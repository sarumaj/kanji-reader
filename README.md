# kanji-reader

A widget helping to learn and memorize Kanji wirtten in Python.

It displays either a Japanese *kanji* character or a Japanese *radical*, its *kunyomi* and *onyomi* readings, and composite radicals as well.
For each character, the JLPT classification is provided.
Futhermore, it provides its *English meaning*.
Just for fun, a *network throughput meter* has been built in as well. 
And of course, the widget can be used as a mere *clock widget*. The widget rotates the displayed character automatically.

Lexical data from [Kradinf](http://nihongo.monash.edu/kradinf.html) and [Kanjidic](http://nihongo.monash.edu/kanjidic2/index.html), and SVG files originating with [KanjiVG project](http://kanjivg.tagaini.net/) are being stored in a SQLite database and reused.

Since tkinter is being used for GUI, currently transparent background is not working on Linux.

## Demo

[Demo](https://github.com/sarumaj/kanji-reader/assets/71898979/fb47966a-1582-4103-8682-19808e04f1d2)

## Build & run

```
git clone https://github.com/sarumaj/kanji-reader
cd kanji-reader
pip install -r requirements.txt
python scripts/build_db.py
python src/app.py
```
