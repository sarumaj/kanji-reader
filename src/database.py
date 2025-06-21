"""
Database management module for the Kanji Reader application.

This module handles all database operations including loading kanji data,
managing settings, and providing data access methods.
"""

import sqlite3
from typing import List, Dict, Any, Optional, Tuple
from config import config


class DatabaseManager:
    """Manages database operations for the Kanji Reader application."""

    def __init__(self, database_path: str = None):
        """
        Initialize the database manager.

        Args:
            database_path: Path to the SQLite database file
        """
        self.database_path = database_path or str(config.paths.database_path)

    def _get_connection(self) -> sqlite3.Connection:
        """Get a database connection with dictionary row factory."""
        conn = sqlite3.connect(self.database_path)
        conn.row_factory = sqlite3.Row
        return conn

    def load_kanji_data(self) -> List[Dict[str, Any]]:
        """
        Load all kanji data from the database.

        Returns:
            List of kanji records as dictionaries
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(config.database_queries.load_kanji)
            return [dict(row) for row in cursor.fetchall()]

    def load_settings(self) -> Dict[str, Any]:
        """
        Load application settings from the database.

        Returns:
            Dictionary containing settings
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(config.database_queries.load_settings)
            row = cursor.fetchone()
            if row:
                return dict(row)
            return {
                'choice': 0,
                'screen0x': 0,
                'screen0y': 0,
                'screen1x': 0,
                'screen1y': 0
            }

    def update_settings(
        self,
        choice: int,
        screen0: Tuple[int, int],
        screen1: Tuple[int, int]
    ) -> None:
        """
        Update application settings in the database.

        Args:
            choice: Current kanji choice index
            screen0: Position for screen 0 (x, y)
            screen1: Position for screen 1 (x, y)
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            values = [choice] + list(screen0) + list(screen1)
            cursor.execute(config.database_queries.update_settings.format(
                choice, ', '.join(map(str, values[1:]))
            ))
            conn.commit()

    def search_kanji_by_character(self, char: str, kanji_data: List[Dict[str, Any]]) -> List[int]:
        """
        Search for kanji by character.

        Args:
            char: Character to search for
            kanji_data: List of kanji data

        Returns:
            List of indices where the character was found
        """
        from utils import encode_character_bytes

        key = encode_character_bytes(char)
        return [
            row for row, _ in enumerate(kanji_data)
            if kanji_data[row]['bytes'] == key
        ]

    def get_kanji_by_index(self, index: int, kanji_data: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """
        Get kanji data by index.

        Args:
            index: Index of the kanji
            kanji_data: List of kanji data

        Returns:
            Kanji data dictionary or None if index is out of range
        """
        if 0 <= index < len(kanji_data):
            return kanji_data[index]
        return None

    def get_available_images(self, kanji_data: Dict[str, Any]) -> List[str]:
        """
        Get list of available image keys for a kanji.

        Args:
            kanji_data: Kanji data dictionary

        Returns:
            List of available image keys
        """
        return [
            f'img_{i}' for i in range(9, -1, -1)
            if kanji_data.get(f'img_{i}')
        ]
