# corak

Procedurally generated geometric wallpapers for Linux desktops. Every image is
drawn from a seed using math — nothing is downloaded, and there is no image
library on disk.

`corak` is Malay for *pattern*.

## Status

Step 3 of 4: setting the desktop background.

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
| Enter | Set as wallpaper |
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
| `grain` | Overlays fine monochrome noise — **expensive**, see below |

`calm` is the quiet mode. What makes a wallpaper distracting is local contrast
between neighbouring shapes rather than overall brightness, so dimming alone
leaves a busy image busy; `calm` flattens shape-to-shape contrast instead, and
forces a dark ground because the effect does not work against a near-white one.

Effects apply in a fixed order regardless of the order they are listed, so the
result never depends on how they were typed. Each is a whole-image composition —
at 3440x1440 a Python pixel loop over five million pixels would dominate the
render, while the full stack costs about 80 ms.

`grain` is off by default and worth thinking about before switching on. Noise is
incompressible, so a grained PNG is roughly twenty times the size of a flat one
— 0.3 MB becomes 7.7 MB at 3440x1440, and a rotation writing one image per
screen turns that into tens of megabytes. Enabling it prints the caveat.

Effects are a render setting rather than part of a `Design`, so changing them
does not invalidate history.

## Desktops

| Shell | Mechanism | Per screen |
| --- | --- | --- |
| KDE Plasma | a script over D-Bus to `org.kde.PlasmaShell` | yes |
| GNOME | `gsettings`, both the light and dark keys | no |
| Xfce | one `xfconf` property per monitor | yes |

Plasma is the only one that can address screens individually without a fight:
`plasma-apply-wallpaperimage` sets a single image everywhere, so per-screen
wallpapers go through the shell's scripting interface and match containments to
screens by logical position. If that fails it falls back to the single-image
command rather than leaving the wallpaper untouched.

Images are rendered at each screen's true panel resolution, so a portrait
monitor gets a portrait image rather than a cropped slice of a widescreen one.
Qt alone is not enough to know that resolution: under Wayland it learns only an
integer buffer scale, so a 1.5x output is reported as 2x and a 3840x1100 panel
looks like 5120x1466. Where KScreen is present its numbers are used instead.

Wallpapers are written to `$XDG_DATA_HOME/corak/wallpapers` rather than a
temporary directory — desktop shells store the path and re-read it at every
login, so an image that vanishes takes the wallpaper with it. Old ones are
pruned after the new one is in place.

## Tests

```sh
.venv/bin/python -m unittest discover -s tests
```
