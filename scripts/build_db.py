# -*- coding: utf-8 -*-
"""
Created on Fri Jan  1 21:32:07 2021

@author: theodave
"""

import xml.etree.ElementTree as ET
import re
import os
import progressbar
import sqlite3
import base64
import json
from pathlib import Path

CURR_DIR = Path(__file__).parent
ROOT = CURR_DIR.parent
SRC_PATH = ROOT / "src"
IMG_PATH = ROOT / "data" / "img"
SVG_PATH = IMG_PATH / "svg"
LEX_PATH = ROOT / "data" / "lex"

# target location
DB_PATH = SRC_PATH / "kanjidic.db"


def SVG_FILES(): return SVG_PATH.glob("*.svg")  # svg files with stroke order


# lex files
KANJIDIC2 = LEX_PATH / "kanjidic2.xml"
KRADFILE2 = LEX_PATH / "kradfile2.utf8"
RADKFILEX = LEX_PATH / "radkfilex.utf8"

# read kradfile2 to get radicals for each kanji
radicals = {
    next(iter(line.split(':'))).strip(): next(iter(line.split(':')[::-1])).split()
    for line in KRADFILE2.read_text().splitlines()
    if not line.startswith('#') and next(iter(line.split(':'))).strip()
}
print("-"*30)
print("BEGIN OF RADICALS")
tuple(print(k, v) for k, v in radicals.items())
print("END OF RADICALS")
print("-"*30)

# read radkfilex to extend the list of kanjis and their radicals
clusters = [
    block for block in '\n'.join([
        line for line in RADKFILEX.read_text().splitlines() if not line.startswith('#')
    ]).split('$') if block
]
for cluster in clusters:
    block = iter(re.split(r"[0-9]", re.sub(r"[\n ]", '', cluster)))
    radical = next(block)
    kanjis = next(block)
    for kanji in kanjis:
        if radical not in radicals.get(kanji, []):
            radicals.update({kanji: radicals.get(kanji, []) + [radical]})

print("-"*30)
print("BEGIN OF CLUSTERS")
tuple(print(cluster) for cluster in clusters)
print("END OF CLUSTERS")
print("-"*30)

# read kanjidic
tree = ET.parse(KANJIDIC2)
root = tree.getroot()

# True: Primary key
# False: Allow NULL as default
properties = json.loads((CURR_DIR / "conf.json").read_text())
print("-"*30)
print("BEGIN OF PROPERTIES")
tuple(print(k, v) for k, v in properties.items())
print("END OF PROPERTIES")
print("-"*30)

# create library table
with sqlite3.connect(DB_PATH) as conn:
    cur = conn.cursor()
    cur.execute('''DROP TABLE IF EXISTS library;''')
    cur.execute('''DROP TABLE IF EXISTS settings;''')
    cur.execute('''CREATE TABLE "settings" (
	"choice"	INTEGER,
	"screen0x"	INTEGER,
	"screen0y"	INTEGER,
	"screen1x"	INTEGER,
	"screen1y"	INTEGER,
	"idx"	INTEGER UNIQUE,
	PRIMARY KEY("idx" AUTOINCREMENT)
);''')
    cur.execute('''INSERT INTO settings (choice, screen0x, screen0y, screen1x, screen1y)
    VALUES (0,0,0,0,0)''')
    cur.execute('''CREATE TABLE library (
        {} , PRIMARY KEY ({})
    );'''.format(
        '\n\t,'.join((
            f"{key} text NOT NULL" if val else f"{key} text" if 'img' not in key else f"{key} blob"
            for key, val in properties.items()
        )),
        ', '.join((key for key, val in properties.items() if val))
    ))


def sqlparser(**kwargs):  # parse data before inserting into the SQL DB
    '''
    Convert:
        list --> basse64 encoded str joined by new line,
        non ascii str --> base64 encoded str.
    '''
    return {
        key: (
            base64.b64encode('\n'.join(val).encode()).decode()
            if isinstance(val, list) else
            val if len(val) == len(val.encode()) else
            base64.b64encode(val.encode()).decode())
        for key, val in kwargs.items() if val
    }


characters = root.findall('character')
# follow up on progress
with progressbar.ProgressBar(max_value=len(characters)) as bar:
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        for idx, character in enumerate(characters):
            char = {}
            '''
            The character itself in UTF8 coding.
            '''
            char['literal'] = getattr(character.find("literal"), 'text', '')
            '''
            Bytes of unicode encoding.
            '''
            char['bytes'] = '/'.join(
                (
                    hex(b) for b in list(
                        getattr(
                            character.find("literal"),
                            'text',
                            ''
                        ).encode('utf-8')
                    )
                )
            )
            '''
            The cp_value contains the codepoint of the character in a particular
        	standard. The standard will be identified in the cp_type attribute.
         
        	The cp_type attribute states the coding standard applying to the
        	element. The values assigned so far are:
        		jis208 - JIS X 0208-1997 - kuten coding (nn-nn)
        		jis212 - JIS X 0212-1990 - kuten coding (nn-nn)
        		jis213 - JIS X 0213-2000 - kuten coding (p-nn-nn)
        		ucs - Unicode 4.0 - hex coding (4 or 5 hexadecimal digits)
            '''
            for val in getattr(character.find("codepoint"), 'findall', lambda *args: [])('cp_value'):
                char['cp_type_{}'.format(
                    getattr(
                        val,
                        'attrib',
                        {}
                    ).get('cp_type')
                )] = getattr(val, 'text', '')
            '''
            The radical number, in the range 1 to 214. The particular
        	classification type is stated in the rad_type attribute.

        	The rad_type attribute states the type of radical classification.
        		classical - based on the system first used in the KangXi Zidian.
        		The Shibano "JIS Kanwa Jiten" is used as the reference source.
        		nelson_c - as used in the Nelson "Modern Japanese-English 
        		Character Dictionary" (i.e. the Classic, not the New Nelson).
        		This will only be used where Nelson reclassified the kanji.
            '''
            for val in getattr(character.find("radical"), 'findall', lambda *args: [])('rad_value'):
                char['rad_type_{}'.format(
                    getattr(
                        val,
                        'attrib',
                        {}
                    ).get('rad_type')
                )] = getattr(val, 'text', '')
            '''
            misc (grade?, stroke_count+, variant*, freq?, rad_name*,jlpt?)
            '''
            misc = character.find('misc')
            '''
            The kanji grade level. 1 through 6 indicates a Kyouiku kanji
        	and the grade in which the kanji is taught in Japanese schools. 
        	8 indicates it is one of the remaining Jouyou Kanji to be learned 
        	in junior high school. 9 indicates it is a Jinmeiyou (for use 
        	in names) kanji which in addition  to the Jouyou kanji are approved 
        	for use in family name registers and other official documents. 10
        	also indicates a Jinmeiyou kanji which is a variant of a
        	Jouyou kanji.
            '''
            char['grade'] = getattr(
                getattr(
                    misc,
                    'find',
                    lambda *args: None
                )('grade'),
                'text',
                ''
            )
            '''
            The stroke count of the kanji, including the radical. If more than 
        	one, the first is considered the accepted count, while subsequent ones 
        	are common miscounts.
            '''
            char['stroke_count'] = getattr(
                getattr(
                    misc,
                    'find',
                    lambda *args: None
                )('stroke_count'),
                'text',
                ''
            )
            '''
            Either a cross-reference code to another kanji, usually regarded as a 
        	variant, or an alternative indexing code for the current kanji.
        	The type of variant is given in the var_type attribute.

        	The var_type attribute indicates the type of variant code. The current
        	values are: 
        		jis208 - in JIS X 0208 - kuten coding
        		jis212 - in JIS X 0212 - kuten coding
        		jis213 - in JIS X 0213 - kuten coding
        		  (most of the above relate to "shinjitai/kyuujitai" 
        		  alternative character glyphs)
        		deroo - De Roo number - numeric
        		njecd - Halpern NJECD index number - numeric
        		s_h - The Kanji Dictionary (Spahn & Hadamitzky) - descriptor
        		nelson_c - "Classic" Nelson - numeric
        		oneill - Japanese Names (O'Neill) - numeric
        		ucs - Unicode codepoint- hex
            '''
            for val in getattr(misc, 'findall', lambda *args: [])('variant'):
                char['var_type_{}'.format(
                    getattr(
                        val,
                        'attrib',
                        {}
                    ).get('var_type')
                )] = getattr(val, 'text', '')
            '''
            A frequency-of-use ranking. The 2,500 most-used characters have a 
        	ranking; those characters that lack this field are not ranked. The 
        	frequency is a number from 1 to 2,500 that expresses the relative 
        	frequency of occurrence of a character in modern Japanese. This is
        	based on a survey in newspapers, so it is biassed towards kanji
        	used in newspaper articles. The discrimination between the less
        	frequently used kanji is not strong. (Actually there are 2,501
        	kanji ranked as there was a tie.)
            '''
            char['frequency'] = getattr(
                getattr(
                    misc,
                    'find',
                    lambda *args: None
                )('freq'),
                'text',
                ''
            )
            '''
            When the kanji is itself a radical and has a name, this element
        	contains the name (in hiragana.)
            '''
            char['radical_name'] = getattr(
                getattr(misc, 'find', lambda *args: None)('rad_name'), 'text', '')
            '''
            The (former) Japanese Language Proficiency test level for this kanji. 
        	Values range from 1 (most advanced) to 4 (most elementary). This field 
        	does not appear for kanji that were not required for any JLPT level.
        	Note that the JLPT test levels changed in 2010, with a new 5-level
        	system (N1 to N5) being introduced. No official kanji lists are
        	available for the new levels. The new levels are regarded as
        	being similar to the old levels except that the old level 2 is
        	now divided between N2 and N3.
            '''
            char['jlpt'] = getattr(
                getattr(
                    misc,
                    'find',
                    lambda *args: None
                )('jlpt'),
                'text',
                ''
            )
            '''
            Each dic_ref contains an index number. The particular dictionary,
        	etc. is defined by the dr_type attribute.

        	The dr_type defines the dictionary or reference book, etc. to which
        	dic_ref element applies. The initial allocation is:
        	  nelson_c - "Modern Reader's Japanese-English Character Dictionary",  
        	  	edited by Andrew Nelson (now published as the "Classic" 
        	  	Nelson).
        	  nelson_n - "The New Nelson Japanese-English Character Dictionary", 
        	  	edited by John Haig.
        	  halpern_njecd - "New Japanese-English Character Dictionary", 
        	  	edited by Jack Halpern.
        	  halpern_kkd - "Kodansha Kanji Dictionary", (2nd Ed. of the NJECD)
        	  	edited by Jack Halpern.
        	  halpern_kkld - "Kanji Learners Dictionary" (Kodansha) edited by 
        	  	Jack Halpern.
        	  halpern_kkld_2ed - "Kanji Learners Dictionary" (Kodansha), 2nd edition
        	    (2013) edited by Jack Halpern.
        	  heisig - "Remembering The  Kanji"  by  James Heisig.
        	  heisig6 - "Remembering The  Kanji, Sixth Ed."  by  James Heisig.
        	  gakken - "A  New Dictionary of Kanji Usage" (Gakken)
        	  oneill_names - "Japanese Names", by P.G. O'Neill. 
        	  oneill_kk - "Essential Kanji" by P.G. O'Neill.
        	  moro - "Daikanwajiten" compiled by Morohashi. For some kanji two
        	  	additional attributes are used: m_vol:  the volume of the
        	  	dictionary in which the kanji is found, and m_page: the page
        	  	number in the volume.
        	  henshall - "A Guide To Remembering Japanese Characters" by
        	  	Kenneth G.  Henshall.
        	  sh_kk - "Kanji and Kana" by Spahn and Hadamitzky.
        	  sh_kk2 - "Kanji and Kana" by Spahn and Hadamitzky (2011 edition).
        	  sakade - "A Guide To Reading and Writing Japanese" edited bysqlparser
        	  	Florence Sakade.
        	  jf_cards - Japanese Kanji Flashcards, by Max Hodges and
        		Tomoko Okazaki. (Series 1)
        	  henshall3 - "A Guide To Reading and Writing Japanese" 3rd
        		edition, edited by Henshall, Seeley and De Groot.
        	  tutt_cards - Tuttle Kanji Cards, compiled by Alexander Kask.
        	  crowley - "The Kanji Way to Japanese Language Power" by
        	  	Dale Crowley.
        	  kanji_in_context - "Kanji in Context" by Nishiguchi and Kono.
        	  busy_people - "Japanese For Busy People" vols I-III, published
        		by the AJLT. The codes are the volume.chapter.
        	  kodansha_compact - the "Kodansha Compact Kanji Guide".
        	  maniette - codes from Yves Maniette's "Les Kanjis dans la tete" French adaptation of Heisig.
            '''
            for val in getattr(character.find("dic_number"), 'findall', lambda *args: [])('dic_ref'):
                char['dr_type_{}'.format(
                    getattr(
                        val,
                        'attrib',
                        {}
                    ).get('dr_type')
                )] = getattr(val, 'text', '')
            '''
            These codes contain information relating to the glyph, and can be used
        	for finding a required kanji. The type of code is defined by the
        	qc_type attribute.
            
            The q_code contains the actual query-code value, according to the
        	qc_type attribute.

        	The qc_type attribute defines the type of query code. The current values
        	are:
        	  skip -  Halpern's SKIP (System  of  Kanji  Indexing  by  Patterns) 
        	  	code. The  format is n-nn-nn.  See the KANJIDIC  documentation 
        	  	for  a description of the code and restrictions on  the 
        	  	commercial  use  of this data. [P]  There are also
        		a number of misclassification codes, indicated by the
        		"skip_misclass" attribute.
        	  sh_desc - the descriptor codes for The Kanji Dictionary (Tuttle 
        	  	1996) by Spahn and Hadamitzky. They are in the form nxnn.n,  
        	  	e.g.  3k11.2, where the  kanji has 3 strokes in the 
        	  	identifying radical, it is radical "k" in the SH 
        	  	classification system, there are 11 other strokes, and it is 
        	  	the 2nd kanji in the 3k11 sequence. (I am very grateful to 
        	  	Mark Spahn for providing the list of these descriptor codes 
        	  	for the kanji in this file.) [I]
        	  four_corner - the "Four Corner" code for the kanji. This is a code 
        	  	invented by Wang Chen in 1928. See the KANJIDIC documentation 
        	  	for  an overview of  the Four Corner System. [Q]
        
        	  deroo - the codes developed by the late Father Joseph De Roo, and 
        	  	published in  his book "2001 Kanji" (Bonjinsha). Fr De Roo 
        	  	gave his permission for these codes to be included. [DR]
        	  misclass - a possible misclassification of the kanji according
        		to one of the code types. (See the "Z" codes in the KANJIDIC
        		documentation for more details.)
        	  
        	The values of this attribute indicate the type if
        	misclassification:
        	- posn - a mistake in the division of the kanji
        	- stroke_count - a mistake in the number of strokes
        	- stroke_and_posn - mistakes in both division and strokes
        	- stroke_diff - ambiguous stroke counts depending on glyph
            '''
            for val in getattr(character.find("query_code"), 'findall', lambda *args: [])('q_code'):
                char['qc_type_{}'.format(
                    getattr(
                        val,
                        'attrib',
                        {}
                    ).get('qc_type')
                )] = getattr(val, 'text', '')
            '''
            The readings for the kanji in several languages, and the meanings, also
        	in several languages. The readings and meanings are grouped to enable
        	the handling of the situation where the meaning is differentiated by 
        	reading.
            '''
            reading_meaning = character.find('reading_meaning')
            '''
            rmgroup (reading*, meaning*)
            '''
            rm_group = getattr(
                reading_meaning,
                'find',
                lambda *args: None
            )('rmgroup')
            '''
            The r_type attribute defines the type of reading in the reading
        	element. The current values are:
        	  pinyin - the modern PinYin romanization of the Chinese reading 
        	  	of the kanji. The tones are represented by a concluding 
        	  	digit. [Y]
        	  korean_r - the romanized form of the Korean reading(s) of the 
        	  	kanji.  The readings are in the (Republic of Korea) Ministry 
        	  	of Education style of romanization. [W]
        	  korean_h - the Korean reading(s) of the kanji in hangul.
        	  vietnam - the Vietnamese readings supplied by Minh Chau Pham.
        	  ja_on - the "on" Japanese reading of the kanji, in katakana. 
        	  	Another attribute r_status, if present, will indicate with
        	  	a value of "jy" whether the reading is approved for a
        	  	"Jouyou kanji".
        		A further attribute on_type, if present,  will indicate with 
        		a value of kan, go, tou or kan'you the type of on-reading.
        	  ja_kun - the "kun" Japanese reading of the kanji, usually in 
        		hiragana. 
        	  	Where relevant the okurigana is also included separated by a 
        	  	".". Readings associated with prefixes and suffixes are 
        	  	marked with a "-". A second attribute r_status, if present, 
        	  	will indicate with a value of "jy" whether the reading is 
        	  	approved for a "Jouyou kanji".
            '''
            for val in getattr(rm_group, 'findall', lambda *args: [])('reading'):
                current_val = list(
                    char.get('reading_type_{}'.format(
                        getattr(
                            val,
                            'attrib',
                            {}
                        ).get('r_type')
                    ), '')
                )
                char['reading_type_{}'.format(
                    getattr(
                        val,
                        'attrib',
                        {}
                    ).get('r_type')
                )] = current_val + [getattr(val, 'text', '')]
            '''
            The meaning associated with the kanji.

        	The m_lang attribute defines the target language of the meaning. It 
        	will be coded using the two-letter language code from the ISO 639-1 
        	standard. When absent, the value "en" (i.e. English) is implied.
            '''
            for val in getattr(rm_group, 'findall', lambda *args: [])('meaning'):
                current_val = list(
                    char.get('meaning_type_{}'.format(
                        getattr(
                            val,
                            'attrib',
                            {}
                        ).get('m_lang', 'en')
                    ), '')
                )
                char['meaning_type_{}'.format(
                    getattr(
                        val,
                        'attrib',
                        {}
                    ).get('m_lang', 'en')
                )] = current_val + [getattr(val, 'text', '')]
            '''
            Japanese readings that are now only associated with names.
            '''
            char['nanori'] = [getattr(n, 'text', '') for n in getattr(
                reading_meaning, 'findall', lambda *args: [])('nanori')]
            '''
            Names of svg files with the strike order for given kanji character.
            Each svg file is being base64 encoded and saved into db.
            '''
            char['svg'] = [
                fname.name for fname in SVG_FILES()
                if char.get('cp_type_ucs').casefold() in fname.name.casefold()
            ]
            for no, svg in enumerate(char.get('svg', [])):
                char[f'img_{no}'] = base64.b64encode(
                    (SVG_PATH / svg).read_bytes()
                ).decode()
            '''
            List of radicals used for construction of given kanji character.
            '''
            char['radicals'] = radicals.get(char.get('literal'), [])
            # insert into database (only if svg file exists)
            assert char.get('cp_type_ucs') and char.get('literal'), \
                'Missing primary key.'

            if char.get('svg'):
                char = sqlparser(**char)
                cur.execute(
                    '''INSERT INTO library ({})
                    VALUES ("{}");'''.format(
                        '\n\t, '.join(char.keys()),
                        '"\n\t, "'.join(char.values())
                    )
                )
            bar.update(idx)
        conn.commit()
