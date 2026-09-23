# Rita-inspired desktop-pet sprites

`rita_sprite_sheet.png` is an original, newly generated 3×2 transparent sprite
sheet made for Codex Usage Pet. It was produced with OpenAI image generation
from a written visual brief after studying public character references; no
official illustration, game texture, fan artwork, logo, or watermark is copied
or embedded.

Frame order:

```text
idle | walk | sit
stretch | critical | sleep
```

Each frame occupies one exact third of the image width and one exact half of
the image height. The code reads the sheet by those normalized cells, so a
replacement asset can use the same layout without changing animation logic.
