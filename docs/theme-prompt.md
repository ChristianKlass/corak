Paste everything below into Gemini (or any chat model), save what it returns,
then run:

    corak --add-theme themes.json

---

I'm generating wallpapers for a Linux desktop. Give me 8 colour themes as a
single JSON array, no prose, no markdown fences.

Each theme is an object with exactly these keys:

  "id"          lowercase single word, unique
  "name"        one or two words, title case
  "description" one short sentence, under 70 characters
  "colors"      5 or 6 hex codes
  "dark"        true if the wallpaper should read as dark, false if light
  "effects"     object, may be empty. Allowed keys: "calm", "darken",
                "vignette", "grain". Values 0.0 to 1.0.
  "scale"       0.7 to 1.7. How large the shapes are.

The single most important rule:

  "colors" is a SET OF DISTINCT COLOURS, not a gradient. Do not give me one hue
  from dark to light. Each entry is used whole, as the colour of a whole shape,
  so a theme of five near-identical blues produces a wallpaper where every shape
  is the same blue and only the brightness differs. That is the failure mode.
  Give me colours that differ in HUE: a teal, a rose, an ochre, a violet. They
  should belong together, the way the colours in a good poster or a film palette
  do, without being neighbours on the wheel.

The rest:

- These are desktop wallpapers, 3440x1440, sitting behind text and windows all
  day. Restraint means dark and low in contrast, NOT desaturated and NOT one
  hue. A grey wallpaper is a failure just as much as a garish one.
- Put real chroma in them. Muddy, washed-out colours are the thing to avoid.
  Deep and rich, not pale and not neon.
- Keep them mostly on the dark side so light text stays readable over them, but
  one or two of the eight can be mid-toned.
- "calm" compresses the tonal range. 0.2 to 0.4 is plenty. Leave it off a theme
  that is already quiet.
- Vary the eight and count as you go. At most three may be warm-dominant
  (browns, reds, ambers) -- an existing set came out five of six warm and the
  whole thing reads as brown. Include at least two that are unmistakably cold
  and one built on green.
- Mean perceptual lightness across a theme's colours should land between 0.35
  and 0.55. Below that everything disappears into the ground.
- Do not use "grain" on more than one theme; it makes files 20x larger.

Think film stills and album covers rather than colour-picker gradients.
