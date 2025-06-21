"""
Main entry point for the Kanji Reader application.

This module provides a clean entry point for the refactored application,
using the new modular structure with separate components for configuration,
database management, UI components, and utilities.
"""

from kanji_app import KanjiApp


def main():
    """Main entry point for the application."""
    try:
        app = KanjiApp()
        app.run()
    except KeyboardInterrupt:
        print("Application interrupted by user")
    except Exception as e:
        print(f"Application error: {e}")
        raise


if __name__ == '__main__':
    main()
