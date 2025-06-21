import xml.etree.ElementTree as ET
import re
import tqdm
import sqlite3
import base64
import logging
from pathlib import Path
from typing import Dict, List, Any, Iterator
from dataclasses import dataclass, asdict


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


@dataclass
class Paths:
    """
    Data class to hold all file and directory paths used in the database build process.

    This centralizes path management and provides type safety for path operations.
    All paths are relative to the script location and follow the project structure.
    """
    curr_dir: Path  # Current script directory
    root: Path      # Project root directory
    src_path: Path  # Source code directory
    img_path: Path  # Image assets directory
    svg_path: Path  # SVG stroke order files directory
    lex_path: Path  # Lexical data files directory
    db_path: Path   # Output database file path


@dataclass
class DatabaseSchema:
    """
    Data class defining the database schema configuration.

    This replaces the conf.json file and defines which fields should be included
    in the library table. Each field has a boolean value:
    - True: Field is a primary key (NOT NULL constraint)
    - False: Field allows NULL values (optional field)

    Special handling exists for 'img' fields which are stored as BLOB data
    for binary image content.
    """
    # Primary key fields (NOT NULL)
    literal: bool = True
    cp_type_ucs: bool = True

    # Basic character information
    bytes: bool = False

    # Codepoint information
    cp_type_jis208: bool = False
    cp_type_jis212: bool = False
    cp_type_jis213: bool = False

    # Radical information
    rad_type_classical: bool = False
    rad_type_nelson_c: bool = False

    # Miscellaneous information
    grade: bool = False
    stroke_count: bool = False
    frequency: bool = False
    radical_name: bool = False
    jlpt: bool = False

    # Variant information
    var_type_jis208: bool = False
    var_type_jis212: bool = False
    var_type_jis213: bool = False
    var_type_deroo: bool = False
    var_type_njecd: bool = False
    var_type_s_h: bool = False
    var_type_nelson_c: bool = False
    var_type_oneill: bool = False
    var_type_ucs: bool = False

    # Dictionary references
    dr_type_nelson_c: bool = False
    dr_type_nelson_n: bool = False
    dr_type_halpern_njecd: bool = False
    dr_type_halpern_kkd: bool = False
    dr_type_halpern_kkld: bool = False
    dr_type_halpern_kkld_2ed: bool = False
    dr_type_heisig: bool = False
    dr_type_heisig6: bool = False
    dr_type_gakken: bool = False
    dr_type_oneill_names: bool = False
    dr_type_oneill_kk: bool = False
    dr_type_moro: bool = False
    dr_type_henshall: bool = False
    dr_type_sh_kk: bool = False
    dr_type_sh_kk2: bool = False
    dr_type_sakade: bool = False
    dr_type_jf_cards: bool = False
    dr_type_henshall3: bool = False
    dr_type_tutt_cards: bool = False
    dr_type_crowley: bool = False
    dr_type_kanji_in_context: bool = False
    dr_type_busy_people: bool = False
    dr_type_kodansha_compact: bool = False
    dr_type_maniette: bool = False

    # Query codes
    qc_type_skip: bool = False
    qc_type_sh_desc: bool = False
    qc_type_four_corner: bool = False
    qc_type_deroo: bool = False
    qc_type_misclass: bool = False

    # Readings
    reading_type_ja_on: bool = False
    reading_type_ja_kun: bool = False
    reading_type_pinyin: bool = False
    reading_type_korean_r: bool = False
    reading_type_korean_h: bool = False
    reading_type_vietnam: bool = False

    # Meanings
    meaning_type_en: bool = False
    meaning_type_fr: bool = False
    meaning_type_de: bool = False
    meaning_type_es: bool = False
    meaning_type_pt: bool = False

    # Additional data
    nanori: bool = False
    radicals: bool = False
    svg: bool = False

    # Image data (BLOB fields)
    img_0: bool = False
    img_1: bool = False
    img_2: bool = False
    img_3: bool = False
    img_4: bool = False
    img_5: bool = False
    img_6: bool = False
    img_7: bool = False
    img_8: bool = False
    img_9: bool = False


class PathManager:
    """Manages file and directory paths for the database build process."""

    def __init__(self):
        self.paths = self._setup_paths()

    def _setup_paths(self) -> Paths:
        """Setup all necessary file paths for the database build process."""
        curr_dir = Path(__file__).parent
        root = curr_dir.parent
        src_path = root / "src"
        img_path = src_path / "data" / "img"
        svg_path = img_path / "svg"
        lex_path = src_path / "data" / "lex"
        db_path = src_path / "kanjidic.db"

        return Paths(
            curr_dir=curr_dir,
            root=root,
            src_path=src_path,
            img_path=img_path,
            svg_path=svg_path,
            lex_path=lex_path,
            db_path=db_path
        )

    def get_svg_files(self) -> Iterator[Path]:
        """Get all SVG files with stroke order from the specified directory."""
        return self.paths.svg_path.glob("*.svg")


class RadicalLoader:
    """Handles loading and processing of radical data from various sources."""

    def __init__(self, lex_path: Path):
        self.lex_path = lex_path

    def load_from_kradfile2(self) -> Dict[str, List[str]]:
        """Load radicals from kradfile2.utf8 file."""
        kradfile2_path = self.lex_path / "kradfile2.utf8"
        radicals: Dict[str, List[str]] = {}

        for line in kradfile2_path.read_text().splitlines():
            if not line.startswith('#') and line.strip():
                parts = line.split(':')
                if len(parts) >= 2:
                    kanji = parts[0].strip()
                    radical_list = parts[-1].split()
                    radicals[kanji] = radical_list

        logger.info("-" * 30)
        logger.info("BEGIN OF RADICALS")
        for k, v in radicals.items():
            logger.info(f"{k} {v}")
        logger.info("END OF RADICALS")
        logger.info("-" * 30)

        return radicals

    def extend_from_radkfilex(self, radicals: Dict[str, List[str]]) -> Dict[str, List[str]]:
        """
        Extend radicals dictionary using radkfilex.utf8 file.

        The radkfilex.utf8 file provides additional radical information that extends
        the base kradfile2 data. It uses a different format with clusters separated
        by '$' characters. Each cluster contains a radical followed by kanji that
        use that radical.

        This function parses the radkfilex format and adds any missing radical
        relationships to the existing radicals dictionary.

        Args:
            radicals (Dict[str, List[str]]): Existing radicals dictionary to extend.

        Returns:
            Dict[str, List[str]]: Extended radicals dictionary with additional mappings.
        """
        radkfilex_path = self.lex_path / "radkfilex.utf8"
        clusters: List[str] = []

        for line in radkfilex_path.read_text().splitlines():
            if not line.startswith('#'):
                clusters.append(line)

        clusters = [
            block for block in '\n'.join(clusters).split('$')
            if block
        ]

        for cluster in clusters:
            block = iter(re.split(r"[0-9]", re.sub(r"[\n ]", '', cluster)))
            radical = next(block)
            kanjis = next(block)
            for kanji in kanjis:
                if radical not in radicals.get(kanji, []):
                    radicals[kanji] = radicals.get(kanji, []) + [radical]

        logger.info("-" * 30)
        logger.info("BEGIN OF CLUSTERS")
        for cluster in clusters:
            logger.info(cluster)
        logger.info("END OF CLUSTERS")
        logger.info("-" * 30)

        return radicals

    def load_all_radicals(self) -> Dict[str, List[str]]:
        """Load and extend radicals from all sources."""
        logger.info("Loading radicals from kradfile2...")
        radicals = self.load_from_kradfile2()

        logger.info("Extending radicals from radkfilex...")
        radicals = self.extend_from_radkfilex(radicals)

        logger.info(f"Loaded radicals for {len(radicals)} kanji")
        return radicals


class DatabaseManager:
    """
    Manages database creation and operations for the kanji database.

    This class is responsible for:
    - Creating the SQLite database tables (settings and library)
    - Inserting kanji character data into the library table
    - Managing schema configuration and table structure
    """

    def __init__(self, db_path: Path, schema: DatabaseSchema):
        """
        Initialize the DatabaseManager.

        Args:
            db_path (Path): Path to the SQLite database file.
            schema (DatabaseSchema): Schema configuration for the library table.
        """
        self.db_path = db_path
        self.schema = schema

    def create_tables(self) -> None:
        """
        Create the database tables for the kanji database.

        This method creates two tables:
        1. 'settings' table: Stores application configuration and UI state.
        2. 'library' table: Stores all kanji character data, with schema defined by the DatabaseSchema dataclass.

        The library table schema is dynamically generated based on the schema configuration. Each field can be:
        - Primary key (NOT NULL constraint)
        - Regular text field (allows NULL)
        - BLOB field (for image data)

        Note:
            This method will drop existing tables if they exist, ensuring a clean database creation.
            The settings table is populated with default values.
        """
        logger.info("Creating database tables...")
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()

            # Drop existing tables
            cur.execute('DROP TABLE IF EXISTS library;')
            cur.execute('DROP TABLE IF EXISTS settings;')

            # Create settings table
            cur.execute(
                'CREATE TABLE "settings" ('
                '    "choice"    INTEGER,'
                '    "screen0x"    INTEGER,'
                '    "screen0y"    INTEGER,'
                '    "screen1x"    INTEGER,'
                '    "screen1y"    INTEGER,'
                '    "idx"    INTEGER UNIQUE,'
                '    PRIMARY KEY("idx" AUTOINCREMENT)'
                ');'
            )

            # Insert default settings
            cur.execute(
                'INSERT INTO settings (choice, screen0x, screen0y, screen1x, screen1y)'
                'VALUES (0,0,0,0,0)'
            )

            # Create library table
            column_descriptors: List[str] = []
            schema_dict = asdict(self.schema)

            for field_name, is_primary_key in schema_dict.items():
                if is_primary_key:
                    column_descriptors.append(f"{field_name} text NOT NULL")
                elif 'img' in field_name:
                    column_descriptors.append(f"{field_name} blob")
                else:
                    column_descriptors.append(f"{field_name} text")

            primary_keys = [field_name for field_name, is_primary_key in schema_dict.items() if is_primary_key]
            cur.execute(
                (
                    'CREATE TABLE library ('
                    '    {columns},'
                    '    PRIMARY KEY ({primary_keys})'
                    ');'
                ).format(
                    columns=',\n    '.join(column_descriptors),
                    primary_keys=', '.join(primary_keys)
                )
            )

        logger.info("Database tables created successfully")

    def insert_character(self, char_data: Dict[str, Any]) -> None:
        """
        Insert a single kanji character record into the library table.

        Args:
            char_data (Dict[str, Any]):
                Dictionary containing character data, with keys matching the library table columns.

        Note:
            The data should be pre-processed and encoded as needed (e.g., using DataProcessor.sqlparser).
        """
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()

            # Prepare column names and values for SQL
            columns = list(char_data.keys())
            placeholders = ', '.join(['?' for _ in columns])
            column_names = ', '.join(columns)

            # Create the SQL query
            sql = f'INSERT INTO library ({column_names}) VALUES ({placeholders})'

            # Execute with values as parameters
            cur.execute(sql, list(char_data.values()))
            conn.commit()


class CharacterParser:
    """
    Handles parsing of individual kanji character data from XML elements.

    This class provides methods to extract all relevant information from a <character> XML element,
    including basic info, codepoints, radicals, miscellaneous metadata, dictionary references,
    query codes, readings, meanings, and SVG stroke order files.
    """

    def __init__(self, svg_path: Path):
        """
        Initialize the CharacterParser.

        Args:
            svg_path (Path): Path to the directory containing SVG stroke order files.
        """
        self.svg_path = svg_path

    def parse_basic_info(self, element: ET.Element) -> Dict[str, str]:
        """
        Parse basic character information from an XML element.

        Extracts:
        - literal: The actual kanji character in UTF-8
        - bytes: Hexadecimal representation of the UTF-8 bytes

        Args:
            element (ET.Element): XML element containing character data.

        Returns:
            Dict[str, str]: Dictionary with basic character information.
        """
        char: Dict[str, str] = {}
        literal_elem = element.find("literal")
        char['literal'] = literal_elem.text if literal_elem is not None else ''
        literal_text = literal_elem.text if literal_elem is not None else ''
        char['bytes'] = '/'.join(hex(b) for b in list(literal_text.encode('utf-8')))
        return char

    def parse_codepoint_info(self, element: ET.Element, character: Dict[str, str]) -> None:
        """
        Parse codepoint information from an XML element and update the character dictionary in-place.

        Extracts codepoint data for various character encoding standards:
        - jis208: JIS X 0208-1997 kuten coding
        - jis212: JIS X 0212-1990 kuten coding
        - jis213: JIS X 0213-2000 kuten coding
        - ucs: Unicode 4.0 hex coding

        Args:
            element (ET.Element): XML element containing character data.
            character (Dict[str, str]): Dictionary to store parsed codepoint information.
        """
        codepoint = element.find("codepoint")
        for val in codepoint.findall('cp_value') if codepoint is not None else []:
            cp_type = val.attrib.get('cp_type')
            if cp_type:
                character[f'cp_type_{cp_type}'] = val.text or ''

    def parse_radical_info(self, element: ET.Element, character: Dict[str, str]) -> None:
        """
        Parse radical information from an XML element and update the character dictionary in-place.

        Extracts radical classification data for different systems:
        - classical: Based on KangXi Zidian system
        - nelson_c: Nelson "Modern Reader's Japanese-English Character Dictionary"

        Args:
            element (ET.Element): XML element containing character data.
            character (Dict[str, str]): Dictionary to store parsed radical information.
        """
        radical = element.find("radical")
        for val in radical.findall('rad_value') if radical is not None else []:
            rad_type = val.attrib.get('rad_type')
            if rad_type:
                character[f'rad_type_{rad_type}'] = val.text or ''

    def parse_misc_info(self, element: ET.Element, character: Dict[str, str]) -> None:
        """
        Parse miscellaneous character information from an XML element and update the character dictionary in-place.

        Extracts:
        - grade: Japanese school grade level (1-6, 8, 9, 10)
        - stroke_count: Number of strokes in the character
        - variant: Alternative character forms and codes
        - frequency: Usage frequency ranking (1-2500)
        - radical_name: Name of the radical in hiragana
        - jlpt: Japanese Language Proficiency Test level (1-4)

        Args:
            element (ET.Element): XML element containing character data.
            character (Dict[str, str]): Dictionary to store parsed miscellaneous information.
        """
        if (misc := element.find('misc')) is None:
            return
        grade_elem = misc.find('grade')
        character['grade'] = grade_elem.text if grade_elem is not None else ''
        stroke_elem = misc.find('stroke_count')
        character['stroke_count'] = stroke_elem.text if stroke_elem is not None else ''
        for val in misc.findall('variant'):
            var_type = val.attrib.get('var_type')
            if var_type:
                character[f'var_type_{var_type}'] = val.text or ''
        freq_elem = misc.find('freq')
        character['frequency'] = freq_elem.text if freq_elem is not None else ''
        rad_name_elem = misc.find('rad_name')
        character['radical_name'] = rad_name_elem.text if rad_name_elem is not None else ''
        jlpt_elem = misc.find('jlpt')
        character['jlpt'] = jlpt_elem.text if jlpt_elem is not None else ''

    def parse_dictionary_references(self, element: ET.Element, character: Dict[str, str]) -> None:
        """
        Parse dictionary reference information from an XML element and update the character dictionary in-place.

        Extracts reference numbers for various kanji dictionaries and learning resources.

        Args:
            element (ET.Element): XML element containing character data.
            character (Dict[str, str]): Dictionary to store parsed dictionary references.
        """
        dic_number = element.find("dic_number")
        for val in dic_number.findall('dic_ref') if dic_number is not None else []:
            dr_type = val.attrib.get('dr_type')
            if dr_type:
                character[f'dr_type_{dr_type}'] = val.text or ''

    def parse_query_codes(self, element: ET.Element, character: Dict[str, str]) -> None:
        """
        Parse query code information from an XML element and update the character dictionary in-place.

        Extracts various indexing and lookup codes for finding kanji:
        - skip: Halpern's SKIP (System of Kanji Indexing by Patterns)
        - sh_desc: Spahn & Hadamitzky descriptor codes
        - four_corner: Four Corner code system
        - deroo: De Roo number system
        - misclass: Possible misclassification codes

        Args:
            element (ET.Element): XML element containing character data.
            character (Dict[str, str]): Dictionary to store parsed query codes.
        """
        query_code = element.find("query_code")
        for val in query_code.findall('q_code') if query_code is not None else []:
            qc_type = val.attrib.get('qc_type')
            if qc_type:
                character[f'qc_type_{qc_type}'] = val.text or ''

    def parse_readings_and_meanings(self, element: ET.Element, character: Dict[str, Any]) -> None:
        """
        Parse readings and meanings information from an XML element and update the character dictionary in-place.

        Extracts readings (ja_on, ja_kun, pinyin, korean, vietnamese) and meanings (in multiple languages),
        as well as nanori (name readings).

        Args:
            element (ET.Element): XML element containing character data.
            character (Dict[str, Any]): Dictionary to store parsed readings and meanings.
        """
        if (reading_meaning := element.find('reading_meaning')) is None:
            return
        rm_group = reading_meaning.find('rmgroup')
        for val in rm_group.findall('reading') if rm_group is not None else []:
            r_type = val.attrib.get('r_type')
            if r_type:
                current_val: List[str] = list(
                    character.get(f'reading_type_{r_type}', '')
                )
                character[f'reading_type_{r_type}'] = (
                    current_val + [val.text or '']
                )
        for val in rm_group.findall('meaning') if rm_group is not None else []:
            m_lang = val.attrib.get('m_lang', 'en')
            current_val: List[str] = list(
                character.get(f'meaning_type_{m_lang}', '')
            )
            character[f'meaning_type_{m_lang}'] = (
                current_val + [val.text or '']
            )
        # Parse nanori (name readings)
        nanori_elements = reading_meaning.findall('nanori')
        character['nanori'] = [elem.text or '' for elem in nanori_elements]

    def parse_svg_files(self, character: Dict[str, Any]) -> None:
        """
        Parse SVG files for the character and encode them as base64.

        Finds SVG stroke order files that match the character's Unicode codepoint
        and encodes them as base64 strings for database storage.
        SVG files are named using the Unicode codepoint (e.g., "4e00.svg" for character "一").

        The function:
        1. Looks for SVG files containing the character's UCS codepoint
        2. Encodes each SVG file as base64
        3. Stores the encoded data with keys 'img_0', 'img_1', etc.
        4. Stores the list of SVG filenames in the 'svg' key

        Args:
            character (Dict[str, Any]): Dictionary containing character data (must have 'cp_type_ucs').
        """
        if not (cp_type_ucs := character.get('cp_type_ucs', '')):
            character['svg'] = []
            return
        character['svg'] = [
            fname.name for fname in self.svg_path.glob("*.svg")
            if cp_type_ucs.casefold() in fname.name.casefold()
        ]
        # Encode SVG files as base64
        for no, svg in enumerate(character.get('svg', [])):
            if (svg_file_path := self.svg_path / svg).exists():
                character[f'img_{no}'] = base64.b64encode(
                    svg_file_path.read_bytes()
                ).decode()

    def parse_character(self, element: ET.Element, radicals: Dict[str, List[str]]) -> Dict[str, Any]:
        """Parse a complete character element from the KANJIDIC XML."""
        character: Dict[str, Any] = {}

        # Parse all character information
        character.update(self.parse_basic_info(element))
        self.parse_codepoint_info(element, character)
        self.parse_radical_info(element, character)
        self.parse_misc_info(element, character)
        self.parse_dictionary_references(element, character)
        self.parse_query_codes(element, character)
        self.parse_readings_and_meanings(element, character)
        self.parse_svg_files(character)

        # Add radicals information
        literal = character.get('literal', '')
        character['radicals'] = radicals.get(literal, [])

        return character


class DataProcessor:
    """Handles data processing and encoding for database storage."""

    @staticmethod
    def sqlparser(**kwargs: Any) -> Dict[str, str]:
        """
        Parse data before inserting into the SQL database.

        This function handles data encoding and conversion for database storage:
        - Lists are joined with newlines and base64 encoded
        - Non-ASCII strings are base64 encoded
        - ASCII strings are left unchanged
        - Empty/None values are filtered out
        """
        new_kwargs: Dict[str, str] = {}
        for key, val in kwargs.items():
            if not val:
                continue
            if isinstance(val, list):
                new_kwargs[key] = base64.b64encode('\n'.join(val).encode()).decode()
            elif len(val) == len(val.encode()):
                new_kwargs[key] = val
            else:
                new_kwargs[key] = base64.b64encode(val.encode()).decode()
        return new_kwargs


class KanjiDatabaseBuilder:
    """Main class that orchestrates the entire database building process."""

    def __init__(self):
        self.path_manager = PathManager()
        self.radical_loader = RadicalLoader(self.path_manager.paths.lex_path)
        self.schema = DatabaseSchema()
        self.db_manager = DatabaseManager(self.path_manager.paths.db_path, self.schema)
        self.character_parser = CharacterParser(self.path_manager.paths.svg_path)
        self.data_processor = DataProcessor()

    def load_xml_data(self) -> List[ET.Element]:
        """Load and parse the KANJIDIC XML file."""
        logger.info("Parsing kanjidic XML...")
        tree: ET.ElementTree = ET.parse(self.path_manager.paths.lex_path / "kanjidic2.xml")
        root: ET.Element = tree.getroot()
        characters: List[ET.Element] = root.findall('character')
        logger.info(f"Found {len(characters)} characters in XML")
        return characters

    def process_characters(self, characters: List[ET.Element], radicals: Dict[str, List[str]]) -> None:
        """Process all characters and insert them into the database."""
        logger.info(f"Processing {len(characters)} characters...")

        processed_count = 0
        for character in tqdm.tqdm(characters, desc="Processing characters"):
            char: Dict[str, Any] = self.character_parser.parse_character(character, radicals)

            # Validate primary key
            assert (
                char.get('cp_type_ucs') and char.get('literal')
            ), 'Missing primary key.'

            # Insert into database (only if svg file exists)
            if char.get('svg'):
                char = self.data_processor.sqlparser(**char)
                self.db_manager.insert_character(char)
                processed_count += 1

        logger.info(f"Successfully processed {processed_count} characters with SVG files")

    def build_database(self) -> None:
        """Main method to build the complete kanji database."""
        logger.info("Starting database build process...")
        logger.info(f"Database will be created at: {self.path_manager.paths.db_path}")

        # Load radicals
        radicals = self.radical_loader.load_all_radicals()

        # Create database tables
        self.db_manager.create_tables()

        # Load and process XML data
        characters = self.load_xml_data()
        self.process_characters(characters, radicals)

        logger.info("Database build completed successfully!")


def main() -> None:
    """Main function to orchestrate the complete database building process."""
    builder = KanjiDatabaseBuilder()
    builder.build_database()


if __name__ == "__main__":
    main()
