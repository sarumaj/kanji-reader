"""
Main application class for the Kanji Reader.

This module contains the main application class that orchestrates
all components including the UI, database, and system tray functionality.
"""

import tkinter as tk
import pystray
from pystray import MenuItem as item
from PIL import Image, ImageTk

from config import config, get_platform_config, get_display_count
from database import DatabaseManager
from ui_components import AntialiasedCanvas, ClockDisplay, Button
from utils import (
    wrap_text, decode_base64_field, get_network_bandwidth,
    svg_to_pil_image, extract_kanji_from_clipboard,
    is_auto_advance_time
)


class KanjiApp:
    """Main application class for the Kanji Reader."""

    def __init__(self):
        """Initialize the application."""
        # Initialize database
        self.db_manager = DatabaseManager()
        self.kanji_data = self.db_manager.load_kanji_data()
        self.settings = self.db_manager.load_settings()

        # Application state
        self.choice = self.settings.get('choice', 0)
        self.screen0 = (self.settings.get('screen0x', 0), self.settings.get('screen0y', 0))
        self.screen1 = (self.settings.get('screen1x', 0), self.settings.get('screen1y', 0))
        self.image_selector = 0
        self.search_phrase = ''
        self.on_top = False
        self.opacity = get_platform_config()['default_opacity']

        # Mouse state
        self.mouse_x = 0
        self.mouse_y = 0

        # Animation IDs
        self.after_ids = {}

        # Initialize UI
        self._setup_window()
        self._setup_ui()
        self._setup_event_handlers()
        self._start_animations()

    def _setup_window(self):
        """Setup the main window."""
        self.root = tk.Tk()
        platform_config = get_platform_config()

        # Platform-specific window setup
        if platform_config['transparency_method'] == 'alpha':
            self.root.overrideredirect(1)
            self.root.wait_visibility(self.root)
            self.root.config(bg='black')
            self.root.wm_attributes('-type', platform_config['window_type'])
            self.root.attributes('-alpha', self.opacity)
        else:
            self.root.wm_attributes('-transparentcolor', config.colors.transparent)
            self.root.config(bg=config.colors.transparent)
            self.root.overrideredirect(1)
            self.root.attributes('-alpha', self.opacity)

        # Window properties
        self.root.call('wm', 'attributes', '.', '-topmost', self.on_top)
        self.root.lift()
        self.root.protocol('WM_DELETE_WINDOW', self.withdraw)

        # Position window
        display_count = get_display_count()
        if display_count > 2:
            self.root.geometry(
                f"{config.ui.window_width}x{config.ui.window_height}+{self.screen1[0]}+{self.screen1[1]}"
            )
        else:
            self.root.geometry(
                f"{config.ui.window_width}x{config.ui.window_height}+{self.screen0[0]}+{self.screen0[1]}"
            )

    def _setup_ui(self):
        """Setup the user interface."""
        # Create canvas
        self.canvas = AntialiasedCanvas(
            self.root,
            width=config.ui.window_width,
            height=config.ui.window_height,
            bg=config.colors.background,
            highlightthickness=0
        )
        self.canvas.pack()

        # Create clock display
        self.clock = ClockDisplay(self.canvas)

        # Create buttons
        self._create_buttons()

        # Create menu
        self._create_menu()

        # Initial paint
        self._paint()

    def _create_buttons(self):
        """Create UI buttons."""
        # Quit button
        self.quit_button = Button(
            self.canvas,
            (config.ui.window_width - 50) // 2, 5,
            50, "—", config.colors.fill_red,
            self.withdraw
        )

        # Previous button
        self.prev_button = Button(
            self.canvas,
            (config.ui.window_width - 50) // 2 - 150, 350,
            50, "<<", config.colors.fill_green,
            self.prev
        )

        # Next button
        self.next_button = Button(
            self.canvas,
            (config.ui.window_width - 50) // 2 + 150, 350,
            50, ">>", config.colors.fill_green,
            self.next
        )

    def _create_menu(self):
        """Create the context menu."""
        self.menu = tk.Menu(self.root, tearoff=0)
        self.menu.add_command(label="Quit", command=self.quit)
        self.menu.add_command(label="ToggleOnTop", command=self.switch)

        # Add image selection menu if multiple images available
        current_kanji = self.db_manager.get_kanji_by_index(self.choice, self.kanji_data)
        if current_kanji:
            image_keys = self.db_manager.get_available_images(current_kanji)
            if len(image_keys) > 1:
                self.image_selection_menu = tk.Menu(self.root, tearoff=0)
                for image_key in image_keys:
                    self.image_selection_menu.add_command(
                        label=image_key,
                        command=lambda key=image_key: self._select_image(key)
                    )
                self.menu.add_cascade(label="Images", menu=self.image_selection_menu)

        self._refresh_search_menu()
        self.menu.add_command(label="Cancel", command=self.menu.unpost)

    def _setup_event_handlers(self):
        """Setup event handlers."""
        # Mouse events
        self.root.bind("<Button-3>", self._do_popup)
        self.root.bind("<B1-Motion>", self._mouse_motion)
        self.root.bind("<Button-1>", self._mouse_press)
        self.root.bind("<ButtonRelease-1>", self._mouse_release)

        # Focus events
        self.root.bind("<FocusOut>", self._reset)
        self.root.bind("<Leave>", self._on_leave)
        self.root.bind("<Enter>", self._awake)
        self.root.bind("<FocusIn>", self._awake)

        # Canvas events
        self.canvas.bind("<Button-1>", self._on_canvas_click)
        self.canvas.bind("<Motion>", self._on_canvas_motion)

    def _start_animations(self):
        """Start animation timers."""
        self.after_ids['update'] = self.root.after(
            config.animation.update_interval, self._update
        )
        self.after_ids['bandwidth'] = self.root.after(
            config.animation.bandwidth_interval, self._monitor_bandwidth
        )
        self.after_ids['fade'] = self.root.after(
            config.animation.auto_advance_interval, self._fade_out
        )

    def _paint(self):
        """Paint the main interface."""
        if not self.root.winfo_exists():
            return

        # Clear existing content
        for widget in self.root.grid_slaves() + self.root.pack_slaves():
            widget.destroy()

        # Recreate canvas
        self.canvas = AntialiasedCanvas(
            self.root,
            width=config.ui.window_width,
            height=config.ui.window_height,
            bg=config.colors.background,
            highlightthickness=0
        )
        self.canvas.pack()

        # Recreate clock
        self.clock = ClockDisplay(self.canvas)

        # Recreate buttons
        self._create_buttons()

        # Draw kanji information
        self._draw_kanji_info()

        # Recreate menu
        self._create_menu()

        # Setup event handlers
        self._setup_event_handlers()

    def _draw_kanji_info(self):
        """Draw kanji information on the canvas."""
        current_kanji = self.db_manager.get_kanji_by_index(self.choice, self.kanji_data)
        if not current_kanji:
            return

        def get_field(field_name: str) -> str:
            """Get and decode a field from the current kanji."""
            return decode_base64_field(current_kanji.get(field_name))

        # Draw kanji image
        image_keys = self.db_manager.get_available_images(current_kanji)
        if image_keys and self.image_selector < len(image_keys):
            selected_image_key = image_keys[self.image_selector]
            svg_data = decode_base64_field(current_kanji[selected_image_key])
            if svg_data:
                try:
                    pil_image = svg_to_pil_image(svg_data)
                    tk_image = ImageTk.PhotoImage(pil_image)
                    self.canvas.create_image(
                        (config.ui.window_width - 150) // 2, 70,
                        anchor=tk.NW,
                        image=tk_image
                    )
                except Exception:
                    pass

        # Draw readings
        self._draw_readings(get_field)

        # Draw metadata
        self._draw_metadata(get_field)

        # Draw radicals and meanings
        self._draw_radicals_and_meanings(get_field)

    def _draw_readings(self, get_field):
        """Draw kanji readings."""
        # On readings
        on_readings = wrap_text(
            get_field('reading_type_ja_on').replace('\n', '、 '),
            **config.text_wrap.on_reading
        )
        for idx, line in enumerate(on_readings):
            self.canvas.create_text(
                config.ui.window_width // 2, 210,
                fill=config.colors.text_maroon,
                font=config.fonts.medium,
                text=line.replace(' ', '')
            )

        # Kun readings
        kun_readings = wrap_text(
            get_field('reading_type_ja_kun').replace('\n', '、 '),
            **config.text_wrap.kun_reading
        )
        for idx, line in enumerate(kun_readings):
            self.canvas.create_text(
                config.ui.window_width // 2, 230 + idx * 20,
                fill=config.colors.text_darkblue,
                font=config.fonts.medium,
                text=line.replace(' ', '')
            )

        # Nanori readings
        nanori = get_field('nanori')
        if nanori:
            nanori_readings = wrap_text(
                nanori.replace('\n', '、 '),
                **config.text_wrap.nanori
            )
            for idx, line in enumerate(nanori_readings):
                self.canvas.create_text(
                    config.ui.window_width // 2, 270 + idx * 20,
                    fill=config.colors.text_darkgreen,
                    font=config.fonts.medium,
                    text=line.replace(' ', '')
                )

    def _draw_metadata(self, get_field):
        """Draw kanji metadata."""
        # JLPT level
        jlpt = get_field('jlpt')
        if jlpt:
            self.canvas.create_text(
                config.ui.window_width // 2 - 110, 170,
                fill=config.colors.text_darkgreen,
                font=config.fonts.small,
                text=f'JLPT: {jlpt}'
            )

        # Grade
        grade = get_field('grade')
        if grade:
            self.canvas.create_text(
                config.ui.window_width // 2 - 120, 190,
                fill=config.colors.text_darkgreen,
                font=config.fonts.small,
                text=f'grade: {grade}'
            )

        # Stroke count
        stroke_count = get_field('stroke_count')
        if stroke_count:
            self.canvas.create_text(
                config.ui.window_width // 2 + 120, 190,
                fill=config.colors.text_red,
                font=config.fonts.small,
                text=f'{stroke_count} strokes'
            )

        # Network bandwidth
        self.bandwidth_text = self.canvas.create_text(
            config.ui.window_width // 2 + 105, 170,
            fill=config.colors.text_darkgreen,
            font=config.fonts.small,
            text=get_network_bandwidth()
        )

    def _draw_radicals_and_meanings(self, get_field):
        """Draw radicals and meanings."""
        # Radicals
        radicals = get_field('radicals')
        if radicals:
            radical_lines = wrap_text(
                radicals.replace('\n', '、'),
                **config.text_wrap.radicals
            )
            for idx, line in enumerate(radical_lines):
                self.canvas.create_text(
                    config.ui.window_width // 2, 320 + idx * 15,
                    fill=config.colors.text_darkblue,
                    font=config.fonts.small,
                    text=line
                )

        # Meanings
        meanings = get_field('meaning_type_en')
        if meanings:
            meaning_lines = wrap_text(
                meanings.replace('\n', ', '),
                **config.text_wrap.meanings
            )
            for idx, line in enumerate(meaning_lines):
                self.canvas.create_text(
                    config.ui.window_width // 2, 335 + idx * 15,
                    fill=config.colors.text_darkblue,
                    font=config.fonts.tiny,
                    text=line
                )

    def _select_image(self, image_key: str):
        """Select a different image for the current kanji."""
        current_kanji = self.db_manager.get_kanji_by_index(self.choice, self.kanji_data)
        if current_kanji:
            image_keys = self.db_manager.get_available_images(current_kanji)
            try:
                self.image_selector = image_keys.index(image_key)
                self._paint()
            except ValueError:
                pass

    def _refresh_search_menu(self):
        """Refresh the search menu with clipboard content."""
        self.search_phrase = extract_kanji_from_clipboard()

        if self.search_phrase and self.menu.winfo_exists():
            try:
                self.menu.delete("Search")
            except Exception:
                pass

            self.clipboard_menu = tk.Menu(self.root, tearoff=0)
            if self.search_phrase != "Failed to open clipboard":
                for idx, char in enumerate(self.search_phrase[:config.search.max_clipboard_items]):
                    self.clipboard_menu.insert_command(
                        idx,
                        label=f"{idx: 2d}: {char}",
                        command=lambda ch=char: self.search(ch)
                    )
            else:
                self.clipboard_menu.insert_command(
                    0,
                    label=self.search_phrase,
                    command=lambda *args: None
                )

            self.menu.insert_cascade(
                1 + int(bool(self.search_phrase)),
                label="Search",
                menu=self.clipboard_menu
            )

    def _do_popup(self, event):
        """Show context menu."""
        if hasattr(self, '_refresh_search_menu'):
            self._refresh_search_menu()
        if self.menu.winfo_exists():
            try:
                self.menu.post(event.x_root, event.y_root)
            finally:
                self.menu.grab_release()

    def _mouse_press(self, event):
        """Handle mouse press."""
        if self.root.winfo_exists():
            self.mouse_x, self.mouse_y = event.x, event.y

    def _mouse_motion(self, event):
        """Handle mouse motion for window dragging."""
        if self.root.winfo_exists():
            offset_x, offset_y = event.x - self.mouse_x, event.y - self.mouse_y
            new_x = self.root.winfo_x() + offset_x
            new_y = self.root.winfo_y() + offset_y
            self.root.geometry(f"+{new_x}+{new_y}")

    def _mouse_release(self, event):
        """Handle mouse release and save position."""
        if self.root.winfo_exists():
            offset_x, offset_y = event.x - self.mouse_x, event.y - self.mouse_y
            new_x = self.root.winfo_x() + offset_x
            new_y = self.root.winfo_y() + offset_y

            # Determine which screen position to save
            if new_x >= 0 and new_y >= 0:
                self.screen0 = (new_x, new_y)
            else:
                self.screen1 = (new_x, new_y)

            # Save to database
            self.db_manager.update_settings(self.choice, self.screen0, self.screen1)

    def _on_canvas_click(self, event):
        """Handle canvas clicks."""
        # Check button clicks
        self.quit_button.handle_click(event.x, event.y)
        self.prev_button.handle_click(event.x, event.y)
        self.next_button.handle_click(event.x, event.y)

    def _on_canvas_motion(self, event):
        """Handle canvas mouse motion for button hover effects."""
        # Update button hover states
        if self.quit_button.is_clicked(event.x, event.y):
            self.quit_button.set_hover_color(config.colors.fill_orange)
        else:
            self.quit_button.reset_color()

        if self.prev_button.is_clicked(event.x, event.y):
            self.prev_button.set_hover_color(config.colors.fill_yellow)
        else:
            self.prev_button.reset_color()

        if self.next_button.is_clicked(event.x, event.y):
            self.next_button.set_hover_color(config.colors.fill_yellow)
        else:
            self.next_button.reset_color()

    def _reset(self, *args):
        """Reset button states."""
        if self.root.winfo_exists():
            self.quit_button.reset_color()
            self.prev_button.reset_color()
            self.next_button.reset_color()

    def _on_leave(self, event):
        """Handle mouse leave event."""
        self._reset()
        if hasattr(self, 'after_ids') and 'fade' in self.after_ids:
            self.root.after_cancel(self.after_ids['fade'])
            self.after_ids['fade'] = self.root.after(
                config.animation.auto_advance_interval, self._fade_out
            )

    def _awake(self, *args):
        """Handle mouse enter/focus events."""
        if self.root.winfo_exists():
            if 'fade' in self.after_ids:
                self.root.after_cancel(self.after_ids['fade'])
            self.opacity = get_platform_config()['default_opacity']
            self.root.attributes('-alpha', self.opacity)
            self.root.update()

    def _fade_out(self):
        """Fade out the window."""
        if self.on_top and self.root.winfo_exists():
            if self.opacity > 0.1:
                self.opacity -= config.animation.fade_speed
            else:
                if 'fade' in self.after_ids:
                    self.root.after_cancel(self.after_ids['fade'])
                return

            self.root.attributes('-alpha', self.opacity)
            self.root.update()
            self.after_ids['fade'] = self.root.after(
                config.animation.fade_interval, self._fade_out
            )

    def _update(self):
        """Update clock and check for auto-advance."""
        if self.root.winfo_exists():
            self.clock.update_clock()

            # Check for auto-advance
            if is_auto_advance_time():
                self.next()

            self.after_ids['update'] = self.root.after(
                config.animation.update_interval, self._update
            )

    def _monitor_bandwidth(self):
        """Update bandwidth display."""
        if hasattr(self, 'bandwidth_text') and self.canvas.winfo_exists():
            self.canvas.itemconfig(self.bandwidth_text, text=get_network_bandwidth())

        if self.root.winfo_exists():
            self.after_ids['bandwidth'] = self.root.after(
                config.animation.bandwidth_interval, self._monitor_bandwidth
            )

    def next(self, *args):
        """Go to next kanji."""
        if self.root.winfo_exists():
            if self.choice < len(self.kanji_data) - 1:
                self.choice += 1
            else:
                self.choice = 0

            self.db_manager.update_settings(self.choice, self.screen0, self.screen1)
            self._paint()

    def prev(self, *args):
        """Go to previous kanji."""
        if self.root.winfo_exists():
            if self.choice > 0:
                self.choice -= 1
            else:
                self.choice = len(self.kanji_data) - 1

            self.db_manager.update_settings(self.choice, self.screen0, self.screen1)
            self._paint()

    def search(self, char: str):
        """Search for a specific kanji character."""
        search_results = self.db_manager.search_kanji_by_character(char, self.kanji_data)
        if search_results:
            self.choice = search_results[0]
            self._paint()

    def switch(self):
        """Toggle window on-top state."""
        self.on_top = not self.on_top
        if self.root.winfo_exists():
            self.root.call('wm', 'attributes', '.', '-topmost', self.on_top)
            self.root.update()

    def withdraw(self):
        """Minimize to system tray."""
        if self.root.winfo_exists():
            self.root.withdraw()
            image = Image.open(config.paths.icon_path)
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

    def show(self):
        """Show the window from system tray."""
        if self.root.winfo_exists():
            self.root.deiconify()
            self.root.lift()
        if hasattr(self, 'icon'):
            self.icon.stop()

    def quit(self):
        """Quit the application."""
        if self.root.winfo_exists():
            # Cancel all timers
            for after_id in self.after_ids.values():
                if after_id:
                    self.root.after_cancel(after_id)

            # Stop system tray icon
            if hasattr(self, 'icon'):
                self.icon.stop()

            self.root.destroy()

    def run(self):
        """Start the application main loop."""
        self.root.mainloop()
