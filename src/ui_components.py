"""
UI Components module for the Kanji Reader application.

This module contains classes for different UI components including
the antialiased canvas, clock display, and button components.
"""

import tkinter as tk
from PIL import ImageTk
from typing import Optional, Callable
from config import config
from utils import draw_ellipse_with_gradient, calculate_clock_position, get_current_time_angles


class AntialiasedCanvas(tk.Canvas):
    """Enhanced canvas with antialiasing support."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def antialias_args(self, args: dict, winc: float = 0.5, cw: int = 2) -> dict:
        """
        Calculate arguments for antialiasing.

        Args:
            args: Original drawing arguments
            winc: Width increment for antialiasing
            cw: Color weight for blending

        Returns:
            Modified arguments for antialiasing
        """
        nargs = {}
        # Set defaults
        nargs['width'] = 1
        nargs['fill'] = "#000"

        # Get original args
        for arg in args:
            nargs[arg] = args[arg]

        if nargs['width'] == 0:
            nargs['width'] = 1

        if nargs.get('arrowshape'):
            nargs['arrowshape'] = tuple(
                map(lambda x: x + winc, nargs['arrowshape'])
            )

        # Calculate width
        nargs['width'] += winc

        # Calculate color
        cbg = self.winfo_rgb(self.cget("bg"))
        cfg = list(self.winfo_rgb(nargs['fill']))
        cfg[0] = (cfg[0] + cbg[0] * cw) / (cw + 1)
        cfg[1] = (cfg[1] + cbg[1] * cw) / (cw + 1)
        cfg[2] = (cfg[2] + cbg[2] * cw) / (cw + 1)
        nargs['fill'] = '#{0:02x}{1:02x}{2:02x}'.format(
            *tuple(
                map(
                    int,
                    (cfg[0] / 256, cfg[1] / 256, cfg[2] / 256)
                )
            )
        )

        return nargs

    def create_line(self, *args, **kwargs):
        """Create antialiased line."""
        if 'winc' in kwargs and 'cw' in kwargs:
            winc = kwargs.pop('winc')
            cw = kwargs.pop('cw')
            nkwargs = self.antialias_args(kwargs, winc, cw)
            shadow = super().create_line(*args, **nkwargs)
            return (super().create_line(*args, **kwargs), shadow)
        return super().create_line(*args, **kwargs)


class ClockDisplay:
    """Handles the clock display component."""

    def __init__(self, canvas: AntialiasedCanvas):
        """
        Initialize the clock display.

        Args:
            canvas: Canvas to draw on
        """
        self.canvas = canvas
        self.sticks = []
        self.antialiasing = []
        self.timer = None
        self._setup_clock()

    def _setup_clock(self):
        """Setup the clock face and hands."""
        # Draw clock face
        self.canvas.create_oval(
            config.ui.clock_center_x - config.clock.lengths[1],
            config.ui.clock_center_y - config.clock.lengths[1],
            config.ui.clock_center_x + config.clock.lengths[1],
            config.ui.clock_center_y + config.clock.lengths[1],
            fill='',
            width=2,
            outline='black'
        )

        # Create background gradient
        bg = draw_ellipse_with_gradient(
            border_width=2,
            size=(350, 350),
            thick=6,
            fill=config.colors.fill_white
        )
        tk_bg = ImageTk.PhotoImage(bg)
        self.canvas.create_image(
            config.ui.clock_center_x - 175 + 1,
            config.ui.clock_center_y - 175 + 1,
            image=tk_bg,
            anchor='nw'
        )

        # Create timer arc
        self.timer = self.canvas.create_arc(
            config.ui.clock_center_x - 50,
            config.ui.clock_center_y - 50,
            config.ui.clock_center_x + 50,
            config.ui.clock_center_y + 50,
            start=90,
            extent=0,
            fill=config.colors.fill_lightgray,
            outline=config.colors.fill_lightgray
        )

        # Draw hour markers
        for i in range(1, 13):
            angle = i * 30
            start_x, start_y = calculate_clock_position(
                angle, config.clock.lengths[1] - config.clock.marker_length,
                config.ui.clock_center_x, config.ui.clock_center_y
            )
            end_x, end_y = calculate_clock_position(
                angle, config.clock.lengths[1],
                config.ui.clock_center_x, config.ui.clock_center_y
            )

            self.canvas.create_line(
                start_x, start_y, end_x, end_y,
                width=2.0,
                fill=config.colors.text_snow,
                smooth=True,
                capstyle='round',
                joinstyle='round',
                splinesteps=12
            )

        # Create clock hands
        self._create_clock_hands()

    def _create_clock_hands(self):
        """Create the clock hands (hour, minute, second)."""
        for i in range(3):
            store, shadow = self.canvas.create_line(
                config.ui.clock_center_x, config.ui.clock_center_y,
                config.ui.clock_center_x + config.clock.lengths[i],
                config.ui.clock_center_y + config.clock.lengths[i],
                width=config.clock.line_width - 2 * i / 2,
                fill=config.colors.fill_darkslategray,
                smooth=True,
                capstyle='round',
                joinstyle='round',
                splinesteps=12,
                arrow='last',
                arrowshape=config.clock.arrowshape[i],
                winc=1.5,
                cw=2
            )
            self.sticks.append(store)
            self.antialiasing.append(shadow)

    def update_clock(self):
        """Update the clock display with current time."""
        hour_angle, minute_angle, second_angle = get_current_time_angles()

        # Update clock hands
        for n, angle in enumerate([hour_angle, minute_angle, second_angle]):
            x, y = self.canvas.coords(self.sticks[n])[0:2]
            cr = [x, y]
            end_x, end_y = calculate_clock_position(
                angle, config.clock.lengths[n],
                config.ui.clock_center_x, config.ui.clock_center_y
            )
            cr.extend([end_x, end_y])

            if self.canvas.winfo_exists():
                self.canvas.coords(self.sticks[n], tuple(cr))
                self.canvas.coords(self.antialiasing[n], tuple(cr))

        # Update timer arc
        if self.canvas.winfo_exists():
            self.canvas.itemconfig(self.timer, extent=-minute_angle)


class Button:
    """Represents a clickable button on the canvas."""

    def __init__(self, canvas: AntialiasedCanvas, x: int, y: int,
                 size: int, text: str, color: str,
                 click_handler: Optional[Callable] = None):
        """
        Initialize a button.

        Args:
            canvas: Canvas to draw on
            x: X coordinate
            y: Y coordinate
            size: Button size
            text: Button text
            color: Button color
            click_handler: Function to call when clicked
        """
        self.canvas = canvas
        self.x = x
        self.y = y
        self.size = size
        self.text = text
        self.color = color
        self.click_handler = click_handler
        self.bg_image = None
        self.bg_image_id = None
        self.text_id = None
        self._create_button()

    def _create_button(self):
        """Create the button visual elements."""
        # Create button outline
        self.canvas.create_oval(
            self.x, self.y,
            self.x + self.size, self.y + self.size,
            fill='',
            width=2,
            outline='black'
        )

        # Create button background
        self._update_background()

        # Create button text
        self.text_id = self.canvas.create_text(
            self.x + self.size // 2,
            self.y + self.size // 2,
            fill=config.colors.text_white,
            font=config.fonts.large,
            text=self.text
        )

    def _update_background(self, color: str = None):
        """Update button background color."""
        if color is None:
            color = self.color

        self.bg_image = draw_ellipse_with_gradient(
            border_width=2,
            size=(self.size, self.size),
            thick=5,
            fill=color
        )
        tk_bg = ImageTk.PhotoImage(self.bg_image)

        if self.bg_image_id:
            self.canvas.delete(self.bg_image_id)

        self.bg_image_id = self.canvas.create_image(
            self.x + 1, self.y + 1,
            image=tk_bg,
            anchor='nw'
        )

    def set_hover_color(self, color: str):
        """Set button color for hover state."""
        self._update_background(color)

    def reset_color(self):
        """Reset button to default color."""
        self._update_background()

    def is_clicked(self, event_x: int, event_y: int) -> bool:
        """Check if button was clicked."""
        center_x = self.x + self.size // 2
        center_y = self.y + self.size // 2
        distance = ((event_x - center_x) ** 2 + (event_y - center_y) ** 2) ** 0.5
        return distance <= self.size // 2

    def handle_click(self, event_x: int, event_y: int):
        """Handle button click."""
        if self.is_clicked(event_x, event_y) and self.click_handler:
            self.click_handler()
