# corak

Procedurally generated geometric wallpapers for Linux desktops. Every image is
drawn from a seed using math — nothing is downloaded, and there is no image
library on disk.

`corak` is Malay for *pattern*.

## Status

Complete: engine, window, effects, desktop integration and automatic rotation.

## Running

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/corak
```

| Command | |
| --- | --- |
| `corak` | open the window |
| `corak --next` | generate and set a wallpaper, no window — what the timer runs |
| `corak --history 20` | the last 20 designs |
| `corak --again [N]` | set the Nth most recent wallpaper again |
| `corak --design SLUG` | set one exact design, named as `--history` prints it |
| `corak --list-patterns` | pattern names |
| `corak --install-desktop` | add corak to the application menu |
| `corak --list-themes` | list themes and where they came from |
| `corak --add-theme FILE` | check a theme document and install it (`-` for stdin) |

`--install-desktop` writes a menu entry pointing at the interpreter that ran it,
so a virtualenv checkout appears in the launcher without a system-wide install.
Put the entry point on `PATH` too if you want the bare command:

```sh
ln -sf "$PWD/.venv/bin/corak" ~/.local/bin/corak
```

## Keys

| Key | Action |
| --- | --- |
| ↑ | New pattern and new colours |
| ← | Back to the previous design |
| → | Same colours, new pattern |
| ↓ | Same pattern and geometry, new colours |
| T | Next theme (Shift+T for the previous one) |
| C | Toggle *calm* |
| D | Toggle *darken* |
| V | Toggle *vignette* |
| G | Toggle *grain* |
| Enter | Set as wallpaper |
| Esc / Q | Quit |

## Design

A wallpaper is fully described by a `Design`: a pattern name plus two
independent seeds, one for geometry and one for colour. Keeping them separate is
what lets ↓ recolour without disturbing the layout and → relayout without
disturbing the colours, and it means a history entry can be reproduced exactly.

The engine paints onto a `QImage` rather than a `QPixmap`. `QImage` has no
GUI-thread affinity, so the same code can back the window, a background thread,
and a headless run under the offscreen platform plugin.

## Automatic rotation

Rotation is a systemd user timer running `corak --next`, not a loop inside the
application. A resident GUI process would have to be autostarted, stay running
and survive crashes to keep a schedule; the timer costs nothing while idle and
comes back after a logout. Turning on *Change the wallpaper automatically* in
the settings window writes `corak.service` and `corak.timer` and enables them.

The tray icon is a small render of the current design rather than a fixed glyph.
It offers the next wallpaper on demand, the window, and settings. Closing the
window hides it to the tray; Quit from the tray menu ends the process.

## Settings and history

Settings live in `$XDG_CONFIG_HOME/corak/settings.json`, written to a temporary
file and moved into place so an interrupted write cannot leave a half-file that
silently resets everything. Unknown keys are ignored and missing ones fall back
to defaults, so a file from a newer version does not stop an older one starting.

Every generated wallpaper is logged to `$XDG_DATA_HOME/corak/history.db`, one
row per screen, holding the pattern, both seeds, the theme, the scheme, the
effects and the image path — enough to rebuild any past wallpaper exactly. When
an image is pruned its row survives with the path cleared, because the design
does not need the file to be reproduced; deleting the row instead meant history
reached back only as far as the dozen images kept on disk.

A design's slug is what the history, the filenames and the window all print, so
it is the identifier already in front of you — `--design` takes it back.

## Themes

A theme is a set of constraints, not a wallpaper. It pins what gives an image
its character — which patterns, which part of the colour wheel, how saturated,
how large the shapes, which effects — and leaves the rest to the seed. Every
image a theme produces is different; they all look related.

| Theme | |
| --- | --- |
| **Abyssal Flare** | Heavy oceanic depths interrupted by a bright coral flash. |
| **Art Deco** | Mid-toned architectural revival with contrasting coral and navy. |
| **Catppuccin** | Soft pastels with a lavender bias. |
| **Crown Jewel** | Deep and saturated gemstone hues set in heavy shadow. |
| **Nightfall** | Cinematic evening hues driven by slate, crimson, and emerald. |
| **Nord** | Arctic blues and muted frost. |
| **Tokyo Night** | Cool neon blues and violets over near-black. |
| **Vintage Cel** | Slightly brighter animated aesthetic with brass and salmon. |

## Colour

Palettes are built from hue relationships rather than random picks: mono,
analogous, complementary, split-complementary and triad. The tight schemes are
weighted more heavily — a triad spread across a whole screen tends to look like
a test card. `Palette.from_hex` accepts explicit colours instead.

Fields are evaluated over the unit square and normalised to span 0 to 1 across
it. Without that a low-frequency field completes less than one cycle over the
image and sits near-constant at whatever its phases happen to give — often
pinned to one end, so every shape takes the same colour and a whole palette
renders as its darkest entry.

Hue and lightness are chosen independently, from spatial fields at different
scales: hue drifts slowly across the whole image while lightness varies shape to
shape. Driving both from one field is what turns a multi-hue scheme into
confetti — a small spatial step crosses a hue boundary and neighbouring shapes
jump from orange to blue.

Ramps live in **OKLab**, not HSL. HSL lightness is not perceptual: equal steps
in it do not look equal, yellows blow out while blues go muddy, and a straight
interpolation between two hues dips toward grey in the middle. Blending is polar
and takes the shorter way round the hue circle, so a triad ramp keeps its colour
through the midpoint. Where a requested colour falls outside sRGB its chroma is
reduced until it fits, rather than each channel being clipped independently —
clipping shifts the hue, which is the thing a perceptual space is there to avoid.

## Composition

A lattice fills every pixel and reads as texture, whatever colours it uses. What
makes a wallpaper look composed is the opposite: a handful of large shapes, more
small ones, clustered somewhere and absent elsewhere, with the background left
visible between them. The `scatter` pattern is built that way — sizes drawn from
a biased distribution so a few dominate, positions rejected against a density
field so they gather and leave the rest of the frame open, and shapes drawn
largest first so the small ones sit in front and the shadows stack correctly.

How crowded a scattered image is has to be measured, not counted. A fixed number
of shapes is dense when they are large and empty when they are small, and the
same number reads differently on every screen shape — so shapes draw against an
area budget, a fraction of the frame, and placement stops when it runs out.
Overlap means the covered area is less than the total, which makes it a budget
rather than a measurement; but it is the quantity that runs out, and stopping
when it does is what keeps the frame open.

Large, well-separated shapes can carry real hue differences. It was small
adjacent cells that turned a multi-hue scheme into confetti, so `scatter` allows
a much wider hue spread than the tiling patterns do.

## The window

The wallpaper takes the whole upper surface and the chrome sits under it as one
quiet bar, because the generated image is the point and the interface around it
is a frame for someone else's picture.

Two things that used to be invisible are now stated. The arrow keys are listed
one per line, since nothing else hinted that the interaction existed. The two
that mirror each other sit together and the odd one out is last; the verbs are
dim and the nouns are not, because what changes between those two lines is the
only part worth reading twice. And the design's identity — theme, pattern, and the two
seeds — is four labelled fields rather than one run of text, with a button to
copy it, because it can be typed back into `corak --design` to recover a
wallpaper.

Settings apply as they are made. A preview redraw costs under thirty
milliseconds, so there is nothing to wait for and no reason to ask anyone to
confirm; the dialog has one button and it closes the window. Only the rotation
settings reach `systemctl`, since everything else runs on every slider tick.

Styling is QSS, which is a subset of CSS: fills, borders, radii, padding, fonts
and widget gradients. No shadows, transforms or animation. The scheme follows
the desktop's own light or dark setting.

## Previewing

The window renders smaller than the screen, so it scales the pixel density down
to match. Features are sized in millimetres, which makes a smaller image a
physically smaller screen: previewed at the target's own density it showed
shapes at roughly twice the size the wallpaper would have, which is not a
preview of anything.

## Depth

Flat fills are what make a generated wallpaper look generated. Three things
change that, and none of them is expensive — they are all QPainter brushes:

- a **large-scale gradient** under everything, giving the image somewhere to be
  bright and somewhere to be dark, which no amount of per-cell variation supplies
- a **gradient across each shape**, lit from one direction shared by the whole
  image, since shapes lit from different angles read as a collage
- a **shadow**. Tiling patterns use three offset translucent copies, faint,
  because there a shadow only ever lands in the seam between two touching tiles
  and anything stronger closes into black webbing. Scattered shapes sit on open
  ground and take a real one: the whole depth band is painted small into its own
  layer and drawn back at full size, giving a penumbra rather than a hard edge,
  with nearer shapes throwing further. Kept fairly tight — softened more, it
  stops reading as a shadow under a shape and becomes a general dimming.

All of it is kept subtle. A strong per-shape gradient stops reading as a lit
surface and starts reading as an inflated bubble — rounded corners on top of one
make it a children's book. Themes carry a `depth` from 0 to 1, so a theme can
still ask for flat fills.

## Scale

Patterns size their features in **millimetres**, taken from each display's
reported physical size. Sizing as a fraction of the width instead makes one
design render at wildly different apparent scales across a mixed set of
monitors: measured on a 3440x1440 ultrawide, a 3840x1100 panel and a rotated
1080x1920 one, hexagons came out 67, 75 and 21 pixels across. In millimetres
they come out 65, 57 and 56.

Some displays report a physical size that describes the panel rather than the
mode in use, giving wildly different horizontal and vertical densities. Where
the two disagree by more than a quarter the reported size is ignored and a
nominal 96 dpi is assumed.

## Effects

| Effect | What it does |
| --- | --- |
| `calm` | Desaturates and squeezes the tonal range toward the low end |
| `darken` | Scales brightness down without crushing the blacks |
| `vignette` | Darkens toward the edges, shaped to the frame's aspect |
| `grain` | Overlays fine monochrome noise — **expensive**, see below |

`calm` desaturates far less on a theme that supplies its own colours. That step
is there to rein in a generated palette, which can come out garish; a palette
somebody chose is already at the saturation they wanted, and taking another
third out of it leaves grey.

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

## Attribution

Several palettes are taken from established editor colour schemes. Colour values
are not the licensable part of a scheme, but the people who chose them deserve
the credit, and anyone redistributing this should know the terms:

| Palette | From | Licence |
| --- | --- | --- |
| Nord | Arctic Ice Studio and Sven Greb | MIT |
| Catppuccin | Catppuccin | MIT |
| Tokyo Night | enkia | MIT |

Each theme carries `source` and `license` fields, shown by `corak --list-themes`.

## Licence

MIT — see [LICENSE](LICENSE). The borrowed palettes above are MIT too, so
nothing here conflicts; keep their credits with any copy that carries them.

## Tests and linting

```sh
.venv/bin/python -m unittest discover -s tests
.venv/bin/python -m pip install -e ".[dev]"
.venv/bin/ruff check src tests
```

Ruff earns its place here for one rule in particular. `F841` catches a value
unpacked and then never used, which is exactly the shape of a bug that cost a
debugging round trip: a blend function unpacked its blue channel into `blue`
and then read `b`, which was still the colour argument.
