#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Jan  3 11:37:05 2021

@author: theodave
"""

# -*- coding: utf-8 -*-
"""
Created on Tue Oct 27 08:17:58 2020

@author: uid40324
"""


import math
import pyperclip
import pystray
from pystray import MenuItem as item
import psutil
import textwrap
from PIL import Image, ImageTk, ImageDraw, ImageFilter, ImageGrab, features
import io
import cairosvg
from sys import platform
import sqlite3
import re
import base64
import time
import tkinter as tk
import os
from pathlib import Path
CURR_DIR = Path(__file__).parent
ROOT = CURR_DIR.parent
ICON = ROOT / "data" / "img" / "ico" / "app.ico"
LIB_DIR = ROOT / "lib"

# monkey patch for backward compability with Pillow 9.5.0
Image.ANTIALIAS = Image.LANCZOS

DISPLAY_COUNT = 0


def get_current_screen_geometry():
    pass


if platform == "linux" or platform == "linux2":
    from Xlib import display
    from Xlib.ext import randr
    _display_ = display.Display(
        os.environ.get("DISPLAY", ":0")
    )
    DISPLAY_COUNT = _display_.screen_count()

    def get_current_screen_geometry():
        resources = randr.get_screen_resources(_display_.screen(0).root)
        for output in resources.outputs:
            params = _display_.xrandr_get_output_info(
                resources.outputs[0],
                resources.config_timestamp
            )
            if not params.crtc:
                continue
            crtc = _display_.xrandr_get_crtc_info(
                params.crtc,
                resources.config_timestamp
            )
            yield (crtc.width, crtc.height)

elif platform == "win32":
    os.environ['path'] += r';{}'.format(LIB_DIR / "win")
    from wmi import WMI
    _wmi_ = WMI()
    DISPLAY_COUNT = len([
        x for x in _wmi_.Win32_PnPEntity(ConfigManagerErrorCode=0) if 'DISPLAY' in str(x)
    ])

    def get_current_screen_geometry():
        image = ImageGrab.grab(all_screens=False)
        yield (image.width, image.height)

else:
    print(f"Platform {platform} is not supported")
    os._exit(os.EX_OSERR)


class AntialiasedCanvas(tk.Canvas):
    def init__(self):
        return super().__init__()

    # Calculate arguments for antialiasing
    def antialias_args(self, args, winc=0.5, cw=2):
        nargs = {}
        # set defaults
        nargs['width'] = 1
        nargs['fill'] = "#000"
        # get original args
        for arg in args:
            nargs[arg] = args[arg]
        if nargs['width'] == 0:
            nargs['width'] = 1
        if nargs.get('arrowshape'):
            nargs['arrowshape'] = tuple(
                map(lambda x: x+winc, nargs['arrowshape']))
        # calculate width
        nargs['width'] += winc
        # calculate color
        cbg = self.winfo_rgb(self.cget("bg"))
        cfg = list(self.winfo_rgb(nargs['fill']))
        cfg[0] = (cfg[0] + cbg[0]*cw)/(cw+1)
        cfg[1] = (cfg[1] + cbg[1]*cw)/(cw+1)
        cfg[2] = (cfg[2] + cbg[2]*cw)/(cw+1)
        nargs['fill'] = '#{0:02x}{1:02x}{2:02x}'.format(
            *tuple(
                map(
                    int,
                    (cfg[0]/256, cfg[1]/256, cfg[2]/256)
                )
            )
        )

        return nargs

    def create_line(self, *args, **kwargs):
        if 'winc' in kwargs and 'cw' in kwargs:
            winc = kwargs.pop('winc')
            cw = kwargs.pop('cw')
            nkwargs = self.antialias_args(kwargs, winc, cw)
            shadow = super(AntialiasedCanvas, self).create_line(
                *args, **nkwargs)
            return (super(AntialiasedCanvas, self).create_line(*args, **kwargs), shadow)
        return super(AntialiasedCanvas, self).create_line(*args, **kwargs)


class App():
    x, y = 0, 0

    def __init__(self):
        self.database = os.sep.join(
            (os.path.dirname(os.path.abspath(__file__)), "kanjidic.db")
        )
        self.search_phrase = ''
        self.image_selector = 0
        with sqlite3.connect(self.database) as conn:
            def dict_factory(cursor, row):
                d = {}
                for idx, col in enumerate(cursor.description):
                    d[col[0]] = row[idx]
                return d
            conn.row_factory = dict_factory
            cur = conn.cursor()
            cur.execute('''SELECT frequency, 
                img_0, img_1, img_2, img_3, img_4, img_5, img_6, img_7, img_8, img_9, 
                bytes,
                cp_type_ucs,
                literal, 
                grade, 
                jlpt, 
                stroke_count, 
                radical_name, 
                meaning_type_en, 
                nanori, 
                radicals,
                reading_type_ja_kun, 
                reading_type_ja_on
            FROM library
            ORDER BY CAST(stroke_count AS INT), CAST(frequency AS INT) DESC;''')
            self.data = cur.fetchall()
            cur.execute(
                "SELECT choice, screen0x, screen0y, screen1x, screen1y FROM settings WHERE idx = 1;"
            )
            settings = cur.fetchone()
            self.choice = settings.get('choice')
            self.screen0 = (settings.get('screen0x'), settings.get('screen0y'))
            self.screen1 = (settings.get('screen1x'), settings.get('screen1y'))
        self.root = tk.Tk()
        self.onTop = False
        if platform in ["linux", "linux2"]:
            self.root.overrideredirect(1)
            self.root.wait_visibility(self.root)
            self.root.config(bg='black')
            self.root.wm_attributes('-type', 'splash')
            self.opacity = .8
            self.root.attributes('-alpha', self.opacity)
        elif platform == "win32":
            self.root.wm_attributes('-transparentcolor', '#abcdef')
            self.root.config(bg='#abcdef')
            self.root.overrideredirect(1)
            self.opacity = .8
            self.root.wm_attributes('-alpha', self.opacity)
        self.root.call('wm', 'attributes', '.', '-topmost', self.onTop)
        self.root.lift()

        self.root.protocol('WM_DELETE_WINDOW', self.withdraw)
        if DISPLAY_COUNT > 2:
            self.root.geometry("400x420+{}+{}".format(*self.screen1))
        else:
            self.root.geometry("400x420+{}+{}".format(*self.screen0))
        self.root.bind("<FocusOut>", self.reset)

        self.__paint()

        self.root.bind("<Button-3>", self.do_popup)
        self.root.bind("<B1-Motion>", self.mouse_motion)
        self.root.bind("<Button-1>", self.mouse_press)
        self.root.bind("<ButtonRelease-1>", self.mouse_release)
        self.compound = lambda ev, s=self: [s.reset(), setattr(
            s, 'after_id_2', s.root.after(500, s.fadeOut))]
        self.root.bind("<Leave>", self.compound)
        self.root.bind("<FocusOut>", self.compound)
        self.root.bind("<Enter>", self.awake)
        self.root.bind("<FocusIn>", self.awake)

        if not hasattr(self, 'after_id_2'):
            self.after_id_2 = self.root.after(500, self.fadeOut)

    def do_popup(self, event):
        if hasattr(self, '_App__refresh_search_menu'):
            self.__refresh_search_menu()
        if self.menu.winfo_exists():
            try:
                self.menu.post(event.x_root, event.y_root)
            finally:
                self.menu.grab_release()

    def get_curr_screen_geometry(self):
        if self.root.winfo_exists():
            resolution_width = self.root.winfo_screenwidth()
            resolution_height = self.root.winfo_screenheight()
            try:
                width, height = next(get_current_screen_geometry())
            except StopIteration:
                return tuple([0] * 4)
            return (width, height, width / resolution_width, height / resolution_height)
        return tuple([0] * 4)

    def mouse_motion(self, event):
        if self.root.winfo_exists():
            if hasattr(self, "after_id"):
                self.root.after_cancel(self.after_id)
                delattr(self, 'after_id')
            offset_x, offset_y = event.x - App.x, event.y - App.y
            new_x = self.root.winfo_x() + offset_x
            new_y = self.root.winfo_y() + offset_y
            self.root.geometry(f"+{new_x}+{new_y}")

    def mouse_press(self, event):
        if self.root.winfo_exists():
            if hasattr(self, "after_id"):
                self.root.after_cancel(self.after_id)
                delattr(self, 'after_id')
            count = time.time()
            App.x, App.y = event.x, event.y

    def mouse_release(self, event):
        if self.root.winfo_exists():
            width, height, _, _ = self.get_curr_screen_geometry()
            offset_x, offset_y = event.x - App.x, event.y - App.y
            new_x = self.root.winfo_x() + offset_x
            new_y = self.root.winfo_y() + offset_y
            if new_x in range(0, width + 1) and new_y in range(0, height + 1):
                self.screen0 = (new_x, new_y)
            else:
                self.screen1 = (new_x, new_y)
            with sqlite3.connect(self.database) as conn:
                cur = conn.cursor()
                cur.execute('''REPLACE INTO settings(idx, choice, screen0x, screen0y, screen1x, screen1y) 
                VALUES(1, {}, {});'''.format(
                    self.choice,
                    ', '.join(map(str, self.screen0 + self.screen1))
                ))
                conn.commit()
            if hasattr(self, '_App__paint'):
                self.after_id = self.root.after(100, self.__update)

    def send_stat(self):
        if not hasattr(self, 'old_value'):
            self.old_value = 0
        self.new_value = psutil.net_io_counters().bytes_sent + \
            psutil.net_io_counters().bytes_recv
        old_value = self.old_value
        self.old_value = self.new_value
        B = float(self.new_value - old_value)*8
        KB = float(1024)
        MB = float(KB ** 2)  # 1,048,576
        GB = float(KB ** 3)  # 1,073,741,824
        if B < KB:
            return '{:.0f} bps'.format(B)
        elif KB <= B < MB:
            return '{:.2f} Kbps'.format(B/KB)
        elif MB <= B < GB:
            return '{:.2f} Mbps'.format(B/MB)
        else:
            return '{:.2f} Gbps'.format(B/GB)

    def __paint(self):
        if self.root.winfo_exists():
            if hasattr(self, "after_id"):
                self.root.after_cancel(self.after_id)
                delattr(self, 'after_id')
            for slave in self.root.grid_slaves() + self.root.pack_slaves():
                slave.destroy()
            for attr in ["menu"]:
                try:
                    getattr(self, attr).destroy()
                except:
                    pass

            def onclick(event):
                if math.sqrt((event.x - self.root.winfo_width()/2)**2 +
                             (event.y - 30)**2) <= 25:
                    self.withdraw()
                elif math.sqrt((event.x - ((self.root.winfo_width()-50)/2 - 150 + 25))**2 +
                               (event.y - 375)**2) <= 25:
                    self.prev()
                elif math.sqrt((event.x - ((self.root.winfo_width()-50)/2 + 150 + 25))**2 +
                               (event.y - 375)**2) <= 25:
                    self.next()

            def moved(event):
                if self.canvas.winfo_exists():
                    if math.sqrt((event.x - self.root.winfo_width()/2)**2 +
                                 (event.y - 30)**2) <= 25:
                        self.button_quit_bg = App.draw_ellipse_with_gradient(
                            border_width=2,
                            size=(
                                50, 50),
                            thick=5,
                            fill='orange'
                        )
                        self.tk_button_quit_bg = ImageTk.PhotoImage(
                            self.button_quit_bg
                        )
                        self.button_quit_bg_img = self.canvas.create_image(
                            (self.root.winfo_width()-50)/2+1,
                            6,
                            image=self.tk_button_quit_bg,
                            anchor='nw'
                        )
                        self.button_quit_text = self.canvas.create_text(
                            self.root.winfo_width()/2,
                            30,
                            fill="white",
                            font="Verdana 20",
                            text="—"
                        )
                    else:
                        self.button_quit_bg = App.draw_ellipse_with_gradient(
                            border_width=2,
                            size=(
                                50, 50),
                            thick=5,
                            fill='red'
                        )
                        self.tk_button_quit_bg = ImageTk.PhotoImage(
                            self.button_quit_bg
                        )
                        self.button_quit_bg_img = self.canvas.create_image(
                            (self.root.winfo_width()-50)/2+1,
                            6,
                            image=self.tk_button_quit_bg,
                            anchor='nw'
                        )
                        self.button_quit_text = self.canvas.create_text(
                            self.root.winfo_width()/2,
                            30,
                            fill="white",
                            font="Verdana 20",
                            text="—"
                        )
                    if math.sqrt(
                        (event.x - ((self.root.winfo_width()-50)/2 - 150 + 25))**2 +
                            (event.y - 375)**2
                    ) <= 25:
                        self.button_prev_bg = App.draw_ellipse_with_gradient(
                            border_width=2,
                            size=(
                                50, 50),
                            thick=6,
                            fill='yellow'
                        )
                        self.tk_button_prev_bg = ImageTk.PhotoImage(
                            self.button_prev_bg
                        )
                        self.button_prev_bg_img = self.canvas.create_image(
                            (self.root.winfo_width()-50)/2 - 150 + 1,
                            351,
                            image=self.tk_button_prev_bg,
                            anchor='nw'
                        )
                        self.prev_button_text = self.canvas.create_text(
                            (self.root.winfo_width()-50)/2 - 150 + 25,
                            375,
                            fill="white",
                            font="Verdana 20",
                            text="<<"
                        )
                    else:
                        self.button_prev_bg = App.draw_ellipse_with_gradient(
                            border_width=2,
                            size=(
                                50, 50),
                            thick=6,
                            fill='green'
                        )
                        self.tk_button_prev_bg = ImageTk.PhotoImage(
                            self.button_prev_bg
                        )
                        self.button_prev_bg_img = self.canvas.create_image(
                            (self.root.winfo_width()-50)/2 - 150 + 1,
                            351,
                            image=self.tk_button_prev_bg,
                            anchor='nw'
                        )
                        self.prev_button_text = self.canvas.create_text(
                            (self.root.winfo_width()-50)/2 - 150 + 25,
                            375,
                            fill="white",
                            font="Verdana 20",
                            text="<<"
                        )
                    if math.sqrt(
                        (event.x - ((self.root.winfo_width()-50)/2 + 150 + 25))**2 +
                        (event.y - 375)**2
                    ) <= 25:
                        self.button_next_bg = App.draw_ellipse_with_gradient(
                            border_width=2,
                            size=(
                                50, 50),
                            thick=6,
                            fill='yellow'
                        )
                        self.tk_button_next_bg = ImageTk.PhotoImage(
                            self.button_next_bg
                        )
                        self.button_next_bg_img = self.canvas.create_image(
                            (self.root.winfo_width()-50)/2 + 150 + 1,
                            351,
                            image=self.tk_button_next_bg,
                            anchor='nw'
                        )
                        self.next_button_text = self.canvas.create_text(
                            (self.root.winfo_width()-50)/2 + 150 + 25,
                            375,
                            fill="white",
                            font="Verdana 20",
                            text=">>"
                        )
                    else:
                        self.button_next_bg = App.draw_ellipse_with_gradient(
                            border_width=2,
                            size=(
                                50, 50),
                            thick=6,
                            fill='green'
                        )
                        self.tk_button_next_bg = ImageTk.PhotoImage(
                            self.button_next_bg
                        )
                        self.button_next_bg_img = self.canvas.create_image(
                            (self.root.winfo_width()-50)/2 + 150 + 1,
                            351,
                            image=self.tk_button_next_bg,
                            anchor='nw'
                        )
                        self.next_button_text = self.canvas.create_text(
                            (self.root.winfo_width()-50)/2 + 150 + 25,
                            375,
                            fill="white",
                            font="Verdana 20",
                            text=">>"
                        )

            def get(key):
                ret = self.data[self.choice][key]
                if ret:
                    try:
                        return base64.b64decode(ret.encode()).decode()
                    except:
                        return ret
                return ''

            def wrap(text, text_width, step, limit=-1):
                def inner(text, text_width, step):
                    if text_width <= 0:
                        return tuple()
                    lines = textwrap.wrap(
                        text,
                        text_width,
                        break_long_words=False
                    )
                    if len(lines) > 1:
                        return lines[0], *wrap('\n'.join(lines[1:]), text_width - step, step)
                    elif len(lines) > 0:
                        return (lines[0], )
                    else:
                        return tuple()
                result = tuple(
                    sorted(
                        inner(text, text_width, step),
                        reverse=True,
                        key=len
                    )
                )
                if limit == -1:
                    limit = len(result)
                return result[:limit]

            self.root.update()
            self.canvas = AntialiasedCanvas(
                self.root,
                width=self.root.winfo_width(),
                height=self.root.winfo_height(),
                bg='#abcdef',
                highlightthickness=0
            )
            '''
            quit button
             
            '''
            self.button_quit = self.canvas.create_oval(
                (self.root.winfo_width()-50)/2,
                5,
                50+(self.root.winfo_width()-50)/2,
                55,
                fill='',
                width=2
            )
            self.button_quit_bg = App.draw_ellipse_with_gradient(
                border_width=2,
                size=(50, 50),
                thick=4,
                fill='red'
            )
            self.tk_button_quit_bg = ImageTk.PhotoImage(self.button_quit_bg)
            self.button_quit_bg_img = self.canvas.create_image(
                (self.root.winfo_width()-50)/2+1,
                6,
                image=self.tk_button_quit_bg,
                anchor='nw'
            )
            self.button_quit_text = self.canvas.create_text(
                self.root.winfo_width()/2,
                30,
                fill="white",
                font="Verdana 20",
                text="—"
            )

            '''
            main
            
            '''
            self.canvas.create_oval(
                (self.root.winfo_width()-350)/2,
                60,
                350+(self.root.winfo_width()-350)/2,
                410,
                fill='',
                width=2,
                outline='black'
            )
            self.bg = App.draw_ellipse_with_gradient(
                border_width=2,
                size=(350, 350),
                thick=6,
                fill='white'
            )
            self.tk_bg = ImageTk.PhotoImage(self.bg)
            self.canvas.create_image(
                (self.root.winfo_width()-350)/2+1,
                61,
                image=self.tk_bg,
                anchor='nw'
            )
            self.timer = self.canvas.create_arc(
                self.root.winfo_width()/2 - 50,
                60 + 175 - 50,
                self.root.winfo_width()/2 + 50,
                60 + 175 + 50,
                start=90,
                extent=-
                time.localtime(
                    time.time()).tm_min*6,
                fill='light gray',
                outline='light gray'
            )
            for i in range(1, 13):
                self.canvas.create_line(
                    self.root.winfo_width()/2 + 160 * math.cos(math.radians(i*30) - math.radians(90)),
                    60 + 175 + 160 *
                    math.sin(math.radians(
                        i*30) - math.radians(90)),
                    self.root.winfo_width()/2 + 175 * math.cos(math.radians(i*30) - math.radians(90)),
                    60 + 175 + 175 *
                    math.sin(math.radians(
                        i*30) - math.radians(90)),
                    width=2.0,
                    fill='snow',
                    smooth=True,
                    capstyle='round',
                    joinstyle='round',
                    splinesteps=12
                )

            self.sticks = []
            self.antialiasing = []
            self.length = (120, 160, 150)
            self.arrowshape = ((12, 16, 6), (15, 18, 8), (10, 13, 5))
            for i in range(3):
                store, shadow = self.canvas.create_line(
                    self.root.winfo_width()/2,
                    60 + 175,
                    self.root.winfo_width()/2 +
                    self.length[i],
                    60 + 175 +
                    self.length[i],
                    width=3.5 - 2 * i / 2,
                    fill='DarkSlateGray3',
                    smooth=True,
                    capstyle='round',
                    joinstyle='round',
                    splinesteps=12,
                    arrow='last',
                    arrowshape=self.arrowshape[i],
                    winc=1.5,
                    cw=2
                )
                self.sticks.append(store)
                self.antialiasing.append(shadow)

            t = time.time()
            now_loc = time.localtime(t)
            mlsec = float("%.9f" % (t % 1,))
            t = time.strptime(str(now_loc.tm_hour), "%H")
            hour = int(time.strftime("%I", t))*30
            now = (hour + 30*now_loc.tm_min/60, now_loc.tm_min*6 +
                   6*now_loc.tm_sec/60, now_loc.tm_sec*6 + 6*mlsec)
            for n, i in enumerate(now):
                x, y = self.canvas.coords(self.sticks[n])[0:2]
                cr = [x, y]
                cr.append(
                    self.length[n] * math.cos(math.radians(i) -
                                              math.radians(90)) + self.root.winfo_width()/2
                )
                cr.append(
                    self.length[n] *
                    math.sin(math.radians(i) - math.radians(90)) + 60 + 175
                )
                self.canvas.coords(self.sticks[n], tuple(cr))
                self.canvas.coords(self.antialiasing[n], tuple(cr))

            self.image_keys = [
                'img_{}'.format(i)
                for i in range(9, -1, -1)
                if self.data[self.choice]['img_{}'.format(i)]
            ]
            self.image_data = cairosvg.svg2png(
                base64.b64decode(
                    self.data[self.choice][self.image_keys[self.image_selector]].encode()
                ).decode(),
                dpi=120,
                output_width=140,
                output_height=140
            )
            self.image = Image.open(io.BytesIO(self.image_data))
            self.tk_image = ImageTk.PhotoImage(self.image)
            self.canvas.create_image(
                (self.root.winfo_width()-150)/2,
                70,
                anchor=tk.NW,
                image=self.tk_image
            )
            for idx, line in enumerate(
                wrap(
                    get('reading_type_ja_on').replace('\n', '、 '),
                    18,
                    2,
                    limit=1
                )
            ):
                self.canvas.create_text(
                    self.root.winfo_width()/2,
                    210,
                    fill="maroon",
                    font="Verdana 14 bold",
                    text=line.replace(' ', '')
                )
            for idx, line in enumerate(
                wrap(
                    get('reading_type_ja_kun').replace('\n', '、 '),
                    19,
                    2,
                    limit=2
                )
            ):
                self.canvas.create_text(
                    self.root.winfo_width()/2,
                    230 + idx * 20,
                    fill="darkblue",
                    font="Verdana 14 bold",
                    text=line.replace(' ', '')
                )

            if get('nanori'):
                for idx, line in enumerate(
                    wrap(
                        get('nanori').replace('\n', '、 '),
                        17,
                        2,
                        limit=2
                    )
                ):
                    self.canvas.create_text(
                        self.root.winfo_width()/2,
                        270 + idx * 20,
                        fill="darkgreen",
                        font="Verdana 14 bold",
                        text=line.replace(' ', '')
                    )
            if get('jlpt'):
                self.canvas.create_text(
                    self.root.winfo_width()/2 - 110,
                    170,
                    fill="darkgreen",
                    font="Verdana 10",
                    text='JLPT: ' + get('jlpt')
                )
            if get('grade'):
                self.canvas.create_text(
                    self.root.winfo_width()/2 - 120,
                    190,
                    fill="darkgreen",
                    font="Verdana 10",
                    text='grade: ' + get('grade')
                )
            self.canvas.create_text(
                self.root.winfo_width()/2 + 120,
                190,
                fill="red",
                font="Verdana 10",
                text=get('stroke_count') + ' strokes'
            )
            self.bandwidth = self.canvas.create_text(
                self.root.winfo_width()/2 + 105,
                170,
                fill="darkgreen",
                font="Verdana 10",
                text=self.send_stat()
            )
            for idx, line in enumerate(
                wrap(
                    get('radicals').replace('\n', '、'),
                    50,
                    2,
                    limit=1
                )
            ):
                self.canvas.create_text(
                    self.root.winfo_width()/2,
                    320 + idx * 15,
                    fill="darkblue",
                    font="Verdana 10 bold",
                    text=line
                )

            for idx, line in enumerate(
                wrap(
                    get('meaning_type_en').replace('\n', ', '),
                    40,
                    3,
                    limit=4
                )
            ):
                self.canvas.create_text(
                    self.root.winfo_width()/2,
                    335 + idx * 15,
                    fill="darkblue",
                    font="Verdana 9",
                    text=line
                )
            '''
            prev button
            
            '''
            self.button_prev = self.canvas.create_oval(
                (self.root.winfo_width()-50)/2 - 150,
                350,
                50 +
                (self.root.winfo_width(
                )-50)/2 - 150,
                400,
                fill='',
                width=2,
                outline='black'
            )
            self.button_prev_bg = App.draw_ellipse_with_gradient(
                border_width=2,
                size=(50, 50),
                thick=6,
                fill='green'
            )
            self.tk_button_prev_bg = ImageTk.PhotoImage(self.button_prev_bg)
            self.button_next_bg_img = self.canvas.create_image(
                (self.root.winfo_width()-50)/2 - 150 + 1,
                351,
                image=self.tk_button_prev_bg,
                anchor='nw'
            )
            self.prev_button_text = self.canvas.create_text(
                (self.root.winfo_width()-50)/2 - 150 + 25,
                375,
                fill="white",
                font="Verdana 20",
                text="<<"
            )

            '''
            next button
            
            '''
            self.button_next = self.canvas.create_oval(
                (self.root.winfo_width()-50)/2 + 150,
                350,
                50 +
                (self.root.winfo_width(
                )-50)/2 + 150,
                400,
                fill='',
                width=2,
                outline='black'
            )
            self.button_next_bg = App.draw_ellipse_with_gradient(
                border_width=2,
                size=(50, 50),
                thick=6,
                fill='green'
            )
            self.tk_button_next_bg = ImageTk.PhotoImage(self.button_next_bg)
            self.button_next_bg_img = self.canvas.create_image(
                (self.root.winfo_width()-50)/2 + 150 + 1,
                351,
                image=self.tk_button_next_bg,
                anchor='nw'
            )
            self.next_button_text = self.canvas.create_text(
                (self.root.winfo_width()-50)/2 + 150 + 25,
                375,
                fill="white",
                font="Verdana 20",
                text=">>"
            )

            self.canvas.bind("<Button-1>", onclick)
            self.canvas.bind("<Motion>", moved)
            self.canvas.bind("<FocusOut>", self.reset)

            self.canvas.pack()

            self.menu = tk.Menu(self.root, tearoff=0)
            self.menu.add_command(label="Quit", command=self.quit)
            self.menu.add_command(label="ToogleOnTop", command=self.switch)
            if len(self.image_keys) > 1:
                self.image_selection_menu = tk.Menu(self.root, tearoff=0)
                for image_key in self.image_keys:
                    self.image_selection_menu.add_command(
                        label=image_key,
                        command=(
                            lambda *args, image_key=image_key, self=self: (
                                setattr(
                                    self,
                                    'image_selector',
                                    self.image_keys.index(image_key)
                                ),
                                self.__paint()
                            )
                        )
                    )
                self.menu.add_cascade(
                    label="Images",
                    menu=self.image_selection_menu
                )
            self.__refresh_search_menu()
            self.menu.add_command(label="Cancel", command=self.menu.unpost)
            self.menu.insert_separator(
                2 + int(bool(self.search_phrase)) +
                int(len(self.image_keys) > 1)
            )
            self.root.update()
            for attr, func in zip(
                ('after_id', 'after_id_4'),
                (self.__update, self.__monitor_bandwidth)
            ):
                setattr(self, attr, self.root.after(100, func))

    def next(self, *args):
        if self.root.winfo_exists():
            if hasattr(self, "after_id"):
                self.root.after_cancel(self.after_id)
            if self.choice < len(self.data) - 1:
                self.choice += 1
            else:
                self.choice = 0
            with sqlite3.connect(self.database) as conn:
                cur = conn.cursor()
                cur.execute('''REPLACE INTO settings(idx, choice, screen0x, screen0y, screen1x, screen1y) 
                VALUES(1, {}, {});'''.format(
                    self.choice,
                    ', '.join(map(str, self.screen0 + self.screen1))
                ))
                conn.commit()
            if hasattr(self, '_App__paint'):
                self.__paint()

    def prev(self, *args):
        if self.root.winfo_exists():
            if hasattr(self, "after_id"):
                self.root.after_cancel(self.after_id)
                delattr(self, 'after_id')
            if self.choice > 0:
                self.choice -= 1
            else:
                self.choice = len(self.data) - 1
            with sqlite3.connect(self.database) as conn:
                cur = conn.cursor()
                cur.execute('''REPLACE INTO settings(idx, choice, screen0x, screen0y, screen1x, screen1y) 
                VALUES(1, {}, {});'''.format(
                    self.choice,
                    ', '.join(map(str, self.screen0 + self.screen1))
                ))
                conn.commit()
            if hasattr(self, '_App__paint'):
                self.__paint()

    def reset(self, *args):
        if self.root.winfo_exists() and hasattr(self, 'canvas') and self.canvas.winfo_exists():
            if hasattr(self, "after_id_2"):
                self.root.after_cancel(self.after_id_2)
                delattr(self, 'after_id_2')

            self.button_quit_bg = App.draw_ellipse_with_gradient(
                border_width=2,
                size=(50, 50),
                thick=5,
                fill='red'
            )
            self.tk_button_quit_bg = ImageTk.PhotoImage(self.button_quit_bg)
            self.button_quit_bg_img = self.canvas.create_image(
                (self.root.winfo_width()-50)/2+1,
                6,
                image=self.tk_button_quit_bg,
                anchor='nw'
            )
            self.button_quit_text = self.canvas.create_text(
                self.root.winfo_width()/2,
                30,
                fill="white",
                font="Verdana 20",
                text="—"
            )
            self.button_prev_bg = App.draw_ellipse_with_gradient(
                border_width=2,
                size=(50, 50),
                thick=6,
                fill='green'
            )
            self.tk_button_prev_bg = ImageTk.PhotoImage(self.button_prev_bg)
            self.button_prev_bg_img = self.canvas.create_image(
                (self.root.winfo_width()-50)/2 - 150 + 1,
                351,
                image=self.tk_button_prev_bg,
                anchor='nw'
            )
            self.prev_button_text = self.canvas.create_text(
                (self.root.winfo_width()-50)/2 - 150 + 25,
                375,
                fill="white",
                font="Verdana 20",
                text="<<"
            )
            self.button_next_bg = App.draw_ellipse_with_gradient(
                border_width=2,
                size=(50, 50),
                thick=6,
                fill='green'
            )
            self.tk_button_next_bg = ImageTk.PhotoImage(self.button_next_bg)
            self.button_next_bg_img = self.canvas.create_image(
                (self.root.winfo_width()-50)/2 + 150 + 1,
                351,
                image=self.tk_button_next_bg,
                anchor='nw'
            )
            self.next_button_text = self.canvas.create_text(
                (self.root.winfo_width()-50)/2 + 150 + 25,
                375,
                fill="white",
                font="Verdana 20",
                text=">>"
            )

    def awake(self, *args):
        if self.root.winfo_exists():
            if hasattr(self, "after_id_2"):
                self.root.after_cancel(self.after_id_2)
                delattr(self, 'after_id_2')
            self.opacity = .8
            self.root.attributes('-alpha', self.opacity)
            self.root.update()

    def fadeOut(self):
        if self.onTop and self.root.winfo_exists():
            if hasattr(self, 'opacity'):
                if self.opacity > 0.1:
                    self.opacity -= 0.0025
                else:
                    if hasattr(self, "after_id_2"):
                        self.root.after_cancel(self.after_id_2)
                        delattr(self, 'after_id_2')
                    return
            else:
                self.opacity = .8
            self.root.attributes('-alpha', self.opacity)
            self.root.update()
            if hasattr(self, 'fadeOut'):
                self.after_id_2 = self.root.after(10, self.fadeOut)

    def quit(self):
        if self.root.winfo_exists():
            for attr in ['after_id', 'after_id_2', 'after_id_3', 'after_id_4']:
                if hasattr(self, attr):
                    self.root.after_cancel(getattr(self, attr))
                    delattr(self, attr)
            if hasattr(self, 'icon'):
                self.icon.stop()
            self.root.destroy()

    def show(self):
        if self.root.winfo_exists():
            self.root.deiconify()
            self.root.lift()
        if hasattr(self, 'icon'):
            self.icon.stop()

    def withdraw(self):
        if self.root.winfo_exists():
            self.root.withdraw()
            image = Image.open(ICON)
            menu = pystray.Menu(
                item('Quit', self.quit),
                item('Show', self.show, default=True)
            )
            self.icon = pystray.Icon(
                "kanji_reader_tray", image, "Kanji Reader", menu
            )
            try:
                self.icon.remove_notification()
            except NotImplementedError as e:
                print(e)

            def call(self):
                if self._menu is not None:
                    try:
                        self._menu(self)
                        self.update_menu()
                    except TypeError:
                        self.show()
            self.icon.__call__ = call
            self.icon.run()

    def switch(self):
        self.onTop = not self.onTop if hasattr(self, 'onTop') else False
        if self.root.winfo_exists() and hasattr(self, '_App__paint'):
            self.root.call('wm', 'attributes', '.', '-topmost', self.onTop)
            self.root.update()

    def search(self, ch):
        key = '/'.join(
            map(
                lambda x: hex(int(''.join(x), 16)),
                zip(*[iter(ch.encode('utf-8').hex())]*2)
            )
        )
        self.search_results = [
            row for row, _ in enumerate(self.data)
            if self.data[row]['bytes'] == key
        ]
        self.choice = next(iter(self.search_results), self.choice)
        if hasattr(self, '_App__paint'):
            self.__paint()

    def __refresh_search_menu(self):
        exception_msg = "Failed to open clipboard"
        try:
            self.search_phrase = ''.join(
                re.findall(
                    u'[\u4E00-\u9FFF]',  # kanji only
                    pyperclip.paste(),
                    re.U
                )
            )
        except:
            self.search_phrase = exception_msg
        if self.search_phrase and self.menu.winfo_exists():
            try:
                self.menu.delete("Search")
            except:
                ...
            self.clipboard_menu = tk.Menu(self.root, tearoff=0)
            if self.search_phrase != exception_msg:
                for idx, ch in enumerate(self.search_phrase[:10]):
                    self.clipboard_menu.insert_command(
                        idx,
                        label=f"{idx: 2d}: {ch}",
                        command=lambda ch=ch, self=self: self.search(ch)
                    )
            else:
                self.clipboard_menu.insert_command(
                    0,
                    label=exception_msg,
                    command=lambda *args: None
                )
            self.menu.insert_cascade(
                1 + int(bool(self.search_phrase)) +
                int(len(self.image_keys) > 1),
                label="Search",
                menu=self.clipboard_menu
            )

    @staticmethod
    def draw_ellipse_with_gradient(border_width, size, thick, fill):
        mask = Image.new(
            "RGBA",
            (size[0]-border_width, size[1]-border_width),
            (0, 0, 0, 255)
        )
        draw = ImageDraw.Draw(mask)
        draw.ellipse((thick, thick, size[0]-thick, size[1]-thick), fill=fill)
        img = mask.filter(ImageFilter.GaussianBlur(thick//2))
        mask2 = Image.new('L', (size[0]-border_width, size[1]-border_width), 0)
        draw2 = ImageDraw.Draw(mask2)
        draw2.ellipse(
            (
                0, 0,
                size[0]-border_width,
                size[1]-border_width
            ),
            fill=255
        )
        img.putalpha(mask2)
        return img

    def __update(self):
        tt = time.time()
        now_loc = time.localtime(tt)
        mlsec = float("%.9f" % (tt % 1,))
        t = time.strptime(str(now_loc.tm_hour), "%H")
        hour = int(time.strftime("%I", t))*30
        now = (hour + 30*now_loc.tm_min/60, now_loc.tm_min*6 +
               6*now_loc.tm_sec/60, now_loc.tm_sec*6 + 6*mlsec)
        # Changing Stick Coordinates
        for n, i in enumerate(now):
            x, y = self.canvas.coords(self.sticks[n])[0:2]
            cr = [x, y]
            cr.append(
                self.length[n] * math.cos(math.radians(i) -
                                          math.radians(90)) + self.root.winfo_width()/2
            )
            cr.append(
                self.length[n] *
                math.sin(math.radians(i) - math.radians(90)) + 60 + 175
            )
            if hasattr(self, 'canvas') and self.canvas.winfo_exists() and hasattr(self.canvas, 'coords'):
                self.canvas.coords(self.sticks[n], tuple(cr))
                self.canvas.coords(self.antialiasing[n], tuple(cr))
        if hasattr(self, 'canvas') and self.canvas.winfo_exists():
            self.canvas.itemconfig(self.timer, extent=-now[1])
        if now_loc.tm_sec == 59 and int(mlsec * 10) == 0 and now_loc.tm_min == 59:
            self.next()
        if self.root.winfo_exists() and hasattr(self, '_App__update'):
            if hasattr(self, 'after_id'):
                self.root.after_cancel(self.after_id)
                delattr(self, 'after_id')
            self.after_id = self.root.after(5, self.__update)

    def __monitor_bandwidth(self):
        if self.canvas.winfo_exists():
            self.canvas.itemconfig(self.bandwidth, text=self.send_stat())
        if self.root.winfo_exists() and hasattr(self, '_App__monitor_bandwidth'):
            if hasattr(self, 'after_id_4'):
                self.root.after_cancel(self.after_id_4)
                delattr(self, 'after_id_4')
            self.after_id_4 = self.root.after(1000, self.__monitor_bandwidth)


if __name__ == '__main__':
    app = App()
    app.root.mainloop()
