Paste everything below into Gemini (or any chat model), then save what it
returns and run:

    corak --add-theme themes.json

---

I'm generating wallpapers for a Linux desktop. Give me 8 colour themes as a
single JSON array, no prose, no markdown fences.

Each theme is an object with exactly these keys:

  "id"          lowercase single word, unique
  "name"        one or two words, title case
  "description" one short sentence, under 70 characters
  "colors"      4 to 6 hex codes, ordered darkest to lightest
  "dark"        true if the wallpaper should read as dark, false if light
  "effects"     object, may be empty. Allowed keys: "calm", "darken",
                "vignette", "grain". Values 0.0 to 1.0.
  "scale"       0.7 to 1.7. How large the shapes are.

Rules that matter:

- These are desktop wallpapers, 3440x1440, sitting behind text and windows all
  day. They must not compete with the foreground. Nothing near-white, no theme
  whose colours are all close to equally bright.
- Restraint means dark and low-contrast, NOT desaturated. A wallpaper that is
  merely grey is a failure. Give each theme at least one colour with real
  saturation in it and let the rest be quiet around it. Two or three of the
  eight should be recognisably a colour from across the room.
- "calm" compresses the tonal range. Use 0.3 to 0.5 on anything that would
  otherwise be busy or bright, and leave it off entirely on a theme that is
  already dark and low-contrast.
- Colours are interpolated between in order, so consecutive entries should be
  neighbours. Avoid a palette that jumps from one hue to its opposite between
  two adjacent entries.
- Avoid hues between yellow and green at middling lightness; they read as khaki.
- Vary the set: some near-monochrome, some with one accent against a neutral
  ground, a couple with genuine hue contrast. No two themes alike.
- Do not use "grain" on more than one theme; it makes files 20x larger.

Aim for the restraint of a good default macOS or KDE wallpaper, not a poster.
