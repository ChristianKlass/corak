# corak

[![checks](https://github.com/ChristianKlass/corak/actions/workflows/checks.yml/badge.svg)](https://github.com/ChristianKlass/corak/actions/workflows/checks.yml)

Procedurally generated geometric wallpapers for Linux. Every image is drawn from
a seed. Nothing is downloaded, and there is no image library on disk.

`corak` is Malay for *pattern*.

## Install

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/corak --install-desktop   # adds it to the application menu
```

PySide6 pulls in its own Qt, so nothing else is needed.

## Keys

| Key | |
|--- |--- |
| ↓ | keep the pattern, reroll the colours |
| → | keep the colours, reroll the pattern |
| ↑ | reroll both |
| ← | back to the previous design |
| Enter | set as wallpaper |
| T / ⇧T | next / previous theme |
| C D V G | toggle calm, darken, vignette, grain |

## Commands

```bash
corak                       # open the window
corak --next                # generate and set one, no window (what the timer runs)
corak --again 3             # set the third-most-recent wallpaper again
corak --design SLUG         # set one exact design, named as --history prints it
corak --history 20          # the last 20 designs
corak --list-themes         # themes, with where each palette came from
corak --list-patterns
corak --add-theme FILE      # check a theme document and install it
```

## Patterns

| Pattern | |
|--- |--- |
| `hexagons` | flat-top hexagonal tiling |
| `triangles` | split rectangles, the low-poly look |
| `waves` | stacked bands, each casting onto the one behind |
| `scatter` | loose shapes over open ground, in depth |
| `bokeh` | overlapping translucent discs, thrown out of focus |
| `constellation` | points joined by lines, mostly empty |
| `flowing` | a few large organic shapes with lit edges |

## Themes

A theme is a set of constraints, not a wallpaper: which patterns, which part of
the colour wheel, how saturated, how large the shapes, which effects. Every image
it produces is different, and they all look related.

| Theme | Palette | |
|--- |--- |--- |
| **Abyssal Flare** | <img src="docs/palettes/abyss.png" alt="" width="150" height="13"> | Heavy oceanic depths interrupted by a bright coral flash. |
| **Art Deco** | <img src="docs/palettes/deco.png" alt="" width="150" height="13"> | Mid-toned architectural revival with contrasting coral and navy. |
| **Catppuccin** | <img src="docs/palettes/catppuccin.png" alt="" width="150" height="13"> | Soft pastels with a lavender bias. |
| **Crown Jewel** | <img src="docs/palettes/jewel.png" alt="" width="150" height="13"> | Deep and saturated gemstone hues set in heavy shadow. |
| **Nightfall** | <img src="docs/palettes/nightfall.png" alt="" width="150" height="13"> | Cinematic evening hues driven by slate, crimson, and emerald. |
| **Nord** | <img src="docs/palettes/nord.png" alt="" width="150" height="13"> | Arctic blues and muted frost, from the editor scheme. |
| **Tokyo Night** | <img src="docs/palettes/tokyo.png" alt="" width="150" height="13"> | Cool neon blues and violets over near-black. |
| **Vintage Cel** | <img src="docs/palettes/vintage.png" alt="" width="150" height="13"> | Slightly brighter animated aesthetic with brass and salmon. |

Adjusting a theme saves a variant and leaves the original alone. Drop your own
into `~/.config/corak/themes/`, or use `--add-theme` to have it checked first.
`docs/theme-prompt.md` is a prompt for getting a set out of a chat model.

```json
{
  "id": "harbour",
  "name": "Harbour",
  "description": "Cold blues against rust.",
  "colors": ["#10202b", "#1d3a4d", "#2f6d84", "#8fb6c4", "#b5622f"],
  "dark": true,
  "effects": { "calm": 0.45 },
  "scale": 1.1
}
```

## Rotation

A systemd user timer runs `corak --next`. Tick *Change the wallpaper
automatically* in the settings window and it writes and enables the units. No
resident process, and it survives a logout.

```bash
systemctl --user status corak.timer
```

## Desktops

| Shell | How | Per screen |
|--- |--- |--- |
| KDE Plasma | a script over D-Bus to `org.kde.PlasmaShell` | yes |
| GNOME | `gsettings`, both the light and dark keys | no |
| Xfce | one `xfconf` property per monitor | yes |

Only Plasma is tested, since it is what I run. The other two are written
against their documented interfaces and have never touched a real session.

## Notes

Things that were not obvious, mostly discovered the hard way.

* **Features are sized in millimetres**, not as a fraction of the frame. Sizing
  by width put the same design at 67, 75 and 21 pixels across on my three
  monitors. Physical size comes from KScreen, because Qt only learns an integer
  buffer scale under Wayland: a 1.5× output reports as 2×, so a 3840×1100 panel
  looks like 5120×1466.

* **Colour lives in OKLab.** HSL lightness is not perceptual, so equal steps do
  not look equal. Blending takes the shorter way round the hue circle for
  generated schemes, and a straight line for a palette somebody chose. Blue to
  rust the polar way passes through green, inventing a colour that is not in the
  set.

* **Hue and lightness come from separate spatial fields.** Driving both from one
  makes a small step across the image cross a hue boundary, and neighbouring
  shapes jump from orange to blue.

* **Fields are normalised.** A low-frequency field completes less than one cycle
  over the frame and sits near-constant at whatever its phases give, usually
  pinned to one end, so a whole palette renders as its darkest colour.

* **Grain writes about 20× larger files.** Noise does not compress: 0.3 MB
  becomes 7.7 MB at 3440×1440.

* **Crowding is an area budget**, not a shape count. The same count is dense
  when the shapes are large and empty when they are small.

* **The preview scales its pixel density with its size.** Previewing at the
  target screen's density showed shapes at twice the size the wallpaper has.

## Attribution

Three palettes come from editor colour schemes. Colour values are not the
licensable part, but the credit is theirs:

| Palette | From | Licence |
|--- |--- |--- |
| Nord | Arctic Ice Studio and Sven Greb | MIT |
| Catppuccin | Catppuccin | MIT |
| Tokyo Night | enkia | MIT |

## Licence

MIT. See [LICENSE](LICENSE).

## Colophon

Written with AI assistance, which is how I work. The direction, the review, and
the judgement about what was good enough are mine.
