[![build_and_release](https://github.com/sarumaj/kanji-reader/actions/workflows/build_and_release.yml/badge.svg)](https://github.com/sarumaj/kanji-reader/actions/workflows/build_and_release.yml)

---

# kanji-reader

A widget helping to learn and memorize Kanji wirtten in Python.

It displays either a Japanese _kanji_ character or a Japanese _radical_, its _kunyomi_ and _onyomi_ readings, and composite radicals as well.
For each character, the JLPT classification is provided.
Futhermore, it provides its _English meaning_.
Just for fun, a _network throughput meter_ has been built in as well.
And of course, the widget can be used as a mere _clock widget_. The widget rotates the displayed character automatically.

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

Alternatively, a Windows installer is available as a [release](https://github.com/sarumaj/kanji-reader/releases/latest).
