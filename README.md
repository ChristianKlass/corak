# corak

Procedurally generated geometric wallpapers for Linux desktops. Every image is
drawn from a seed using math — nothing is downloaded, and there is no image
library on disk.

`corak` is Malay for *pattern*.

## Status

Step 2 of 4: colour schemes and the effects layer.

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
| C | Toggle *calm* |
| D | Toggle *darken* |
| V | Toggle *vignette* |
| G | Toggle *grain* |
| Esc / Q | Quit |

## Design

A wallpaper is fully described by a `Design`: a pattern name plus two
independent seeds, one for geometry and one for colour. Keeping them separate is
what lets ← recolour without disturbing the layout and → relayout without
disturbing the colours, and it means a history entry can be reproduced exactly.

The engine paints onto a `QImage` rather than a `QPixmap`. `QImage` has no
GUI-thread affinity, so the same code can back the window, a background thread,
and a headless run under the offscreen platform plugin.

## Colour

Palettes are built from hue relationships rather than random picks: mono,
analogous, complementary, split-complementary and triad. The tight schemes are
weighted more heavily — a triad spread across a whole screen tends to look like
a test card. `Palette.from_hex` accepts explicit colours instead.

## Effects

| Effect | What it does |
| --- | --- |
| `calm` | Desaturates and squeezes the tonal range toward the low end |
| `darken` | Scales brightness down without crushing the blacks |
| `vignette` | Darkens toward the edges, shaped to the frame's aspect |
| `grain` | Overlays fine monochrome noise |

`calm` is the quiet mode. What makes a wallpaper distracting is local contrast
between neighbouring shapes rather than overall brightness, so dimming alone
leaves a busy image busy; `calm` flattens shape-to-shape contrast instead, and
forces a dark ground because the effect does not work against a near-white one.

Effects apply in a fixed order regardless of the order they are listed, so the
result never depends on how they were typed. Each is a whole-image composition —
at 3440x1440 a Python pixel loop over five million pixels would dominate the
render, while the full stack costs about 80 ms.

Effects are a render setting rather than part of a `Design`, so changing them
does not invalidate history.

## Tests

```sh
.venv/bin/python -m unittest discover -s tests
```
