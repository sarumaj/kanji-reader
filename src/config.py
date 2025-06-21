"""
Configuration module for the Kanji Reader application.

This module centralizes all configuration constants and settings
used throughout the application using dataclasses for type safety.
"""

import os
from pathlib import Path
from sys import platform
from dataclasses import dataclass, field, asdict
from typing import Dict, Tuple, Any


@dataclass
class Paths:
    """Configuration for file and directory paths."""
    curr_dir: Path = field(default_factory=lambda: Path(__file__).parent)
    icon_path: Path = field(default_factory=lambda: Path(__file__).parent / "data" / "img" / "ico" / "app.ico")
    lib_dir: Path = field(default_factory=lambda: Path(__file__).parent / "lib")
    database_path: Path = field(default_factory=lambda: Path(__file__).parent / "kanjidic.db")


@dataclass
class UIConfig:
    """Configuration for UI dimensions and layout."""
    window_width: int = 400
    window_height: int = 420
    clock_radius: int = 175
    clock_center_x: int = field(init=False)
    clock_center_y: int = field(init=False)

    def __post_init__(self):
        self.clock_center_x = self.window_width // 2
        self.clock_center_y = 60 + self.clock_radius


@dataclass
class Colors:
    """Configuration for application colors."""
    background: str = '#abcdef'
    transparent: str = '#abcdef'
    text_maroon: str = 'maroon'
    text_darkblue: str = 'darkblue'
    text_darkgreen: str = 'darkgreen'
    text_red: str = 'red'
    text_white: str = 'white'
    text_snow: str = 'snow'
    fill_red: str = 'red'
    fill_green: str = 'green'
    fill_yellow: str = 'yellow'
    fill_orange: str = 'orange'
    fill_lightgray: str = 'light gray'
    fill_darkslategray: str = 'DarkSlateGray3'
    fill_white: str = 'white'


@dataclass
class Fonts:
    """Configuration for application fonts."""
    large: str = 'Verdana 20'
    medium: str = 'Verdana 14 bold'
    small: str = 'Verdana 10'
    tiny: str = 'Verdana 9'


@dataclass
class ClockConfig:
    """Configuration for clock display."""
    lengths: Tuple[int, int, int] = (120, 160, 150)
    arrowshape: Tuple[Tuple[int, int, int], Tuple[int, int, int], Tuple[int, int, int]] = (
        (12, 16, 6), (15, 18, 8), (10, 13, 5)
    )
    line_width: float = 3.5
    marker_length: int = 15


@dataclass
class TextWrapConfig:
    """Configuration for text wrapping."""
    on_reading: Dict[str, int] = field(default_factory=lambda: {'width': 18, 'step': 2, 'limit': 1})
    kun_reading: Dict[str, int] = field(default_factory=lambda: {'width': 19, 'step': 2, 'limit': 2})
    nanori: Dict[str, int] = field(default_factory=lambda: {'width': 17, 'step': 2, 'limit': 2})
    radicals: Dict[str, int] = field(default_factory=lambda: {'width': 50, 'step': 2, 'limit': 1})
    meanings: Dict[str, int] = field(default_factory=lambda: {'width': 40, 'step': 3, 'limit': 4})


@dataclass
class PlatformConfig:
    """Configuration for platform-specific settings."""
    window_type: str = 'splash'
    transparency_method: str = 'alpha'
    default_opacity: float = 0.8


@dataclass
class DatabaseQueries:
    """Configuration for database queries."""
    load_kanji: str = '''
        SELECT frequency,
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
        ORDER BY CAST(stroke_count AS INT), CAST(frequency AS INT) DESC
    '''
    load_settings: str = 'SELECT choice, screen0x, screen0y, screen1x, screen1y FROM settings WHERE idx = 1'
    update_settings: str = '''
        REPLACE INTO settings(idx, choice, screen0x, screen0y, screen1x, screen1y)
        VALUES(1, {}, {})
    '''


@dataclass
class AnimationConfig:
    """Configuration for animation settings."""
    fade_speed: float = 0.0025
    fade_interval: int = 10
    update_interval: int = 5
    bandwidth_interval: int = 1000
    auto_advance_interval: int = 500


@dataclass
class SearchConfig:
    """Configuration for search functionality."""
    max_clipboard_items: int = 10
    kanji_regex: str = r'[\u4E00-\u9FFF]'


@dataclass
class AppConfig:
    """Main application configuration combining all settings."""
    paths: Paths = field(default_factory=Paths)
    ui: UIConfig = field(default_factory=UIConfig)
    colors: Colors = field(default_factory=Colors)
    fonts: Fonts = field(default_factory=Fonts)
    clock: ClockConfig = field(default_factory=ClockConfig)
    text_wrap: TextWrapConfig = field(default_factory=TextWrapConfig)
    database_queries: DatabaseQueries = field(default_factory=DatabaseQueries)
    animation: AnimationConfig = field(default_factory=AnimationConfig)
    search: SearchConfig = field(default_factory=SearchConfig)

    # Platform-specific configurations
    linux_config: PlatformConfig = field(default_factory=lambda: PlatformConfig(
        window_type='splash',
        transparency_method='alpha',
        default_opacity=0.8
    ))
    win32_config: PlatformConfig = field(default_factory=lambda: PlatformConfig(
        window_type='normal',
        transparency_method='transparentcolor',
        default_opacity=0.8
    ))


# Global configuration instance
config = AppConfig()

# Convenience accessors for backward compatibility
CURR_DIR = config.paths.curr_dir
ICON_PATH = config.paths.icon_path
LIB_DIR = config.paths.lib_dir
DATABASE_PATH = config.paths.database_path

WINDOW_WIDTH = config.ui.window_width
WINDOW_HEIGHT = config.ui.window_height
CLOCK_RADIUS = config.ui.clock_radius
CLOCK_CENTER_X = config.ui.clock_center_x
CLOCK_CENTER_Y = config.ui.clock_center_y

COLORS = asdict(config.colors)
FONTS = asdict(config.fonts)
CLOCK_CONFIG = asdict(config.clock)
TEXT_WRAP_CONFIG = asdict(config.text_wrap)
DATABASE_QUERIES = asdict(config.database_queries)
ANIMATION_CONFIG = asdict(config.animation)
SEARCH_CONFIG = asdict(config.search)

PLATFORM_CONFIG = {
    'linux': asdict(config.linux_config),
    'win32': asdict(config.win32_config)
}


def get_platform_config() -> Dict[str, Any]:
    """Get platform-specific configuration."""
    if platform in ("linux", "linux2"):
        return asdict(config.linux_config)
    elif platform == "win32":
        return asdict(config.win32_config)
    else:
        raise OSError(f"Platform {platform} is not supported")


def get_display_count() -> int:
    """Get the number of displays for the current platform."""
    if platform in ("linux", "linux2"):
        from Xlib import display
        _display_ = display.Display(os.environ.get("DISPLAY", ":0"))
        return _display_.screen_count()
    elif platform == "win32":
        os.environ['path'] += r';{}'.format(config.paths.lib_dir / "win")
        from wmi import WMI
        _wmi_ = WMI()
        return len([
            x for x in _wmi_.Win32_PnPEntity(ConfigManagerErrorCode=0)
            if 'DISPLAY' in str(x)
        ])
    else:
        return 0
