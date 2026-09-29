# Rita-inspired desktop-pet Skin Pack

`rita_sprite_sheet.png` is an original, newly generated 3×2 transparent sprite
sheet made for Rita Desktop Pet. It was produced with OpenAI image generation
from a written visual brief after studying public character references; no
official illustration, game texture, fan artwork, logo, or watermark is copied
or embedded.

Frame order:

```text
idle | walk | sit
stretch | critical | sleep
```

The frame mapping, theme, size, anchors, per-pose optical offsets, and optional
`frame_durations_ms` timing are declared in `skin.json`. The runtime `stretch`
slot intentionally uses the subtler `animations/tidy_hair.png`; LOW enters the
real seated pose through `animations/sit_transition.png`. Contact sheets,
motion previews, and alpha/anchor validation are under
`artifacts/animations/rita_umbral_rose/`.

A replacement Skin Pack can use individual PNG files or a grid-based sprite
sheet without changing application code.
