# corak

Procedurally generated geometric wallpapers for Linux desktops. Every image is
drawn from a seed using math — nothing is downloaded, and there is no image
library on disk.

`corak` is Malay for *pattern*.

## Status

Step 1 of 4: rendering engine and interactive window.

## Running

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/corak
```

## Keys

| Key | Action |
| --- | --- |
| ↑ | New pattern and new colours |
| ← | Same pattern, new colours |
| → | Same colours, new pattern |
| ↓ | Back to the previous design |
| Esc / Q | Quit |

## Design

A wallpaper is fully described by a `Design`: a pattern name plus two
independent seeds, one for geometry and one for colour. Keeping them separate is
what lets ← recolour without disturbing the layout and → relayout without
disturbing the colours, and it means a history entry can be reproduced exactly.

The engine paints onto a `QImage` rather than a `QPixmap`. `QImage` has no
GUI-thread affinity, so the same code can back the window, a background thread,
and a headless run under the offscreen platform plugin.

## Tests

```sh
.venv/bin/python -m unittest discover -s tests
```
