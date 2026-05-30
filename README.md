\# محرك الخط — Khatt Engine



\*\*Linguistically sovereign Arabic calligraphy generation.\*\*



Khatt Engine is an open, modular pipeline that generates

correct Arabic calligraphy by separating linguistic responsibility

from aesthetic responsibility. The writing is done by mathematics.

The painting is done by AI.



\---



\## The Problem



Every major AI image generator — Stable Diffusion, DALL-E,

Midjourney, Firefly — fails at Arabic calligraphy. Not because

they lack training data. Because they have a category error baked

into their architecture.



When you ask them to write بسم الله in Thuluth style, they do not

look up the letters, apply the grammar of the script, or consult

any calligraphic rules. They retrieve a statistical pattern from

training data that \*resembles\* Arabic writing. The letters may be

wrong. The dots may be missing. The proportions are fabricated.

But it looks right to someone who cannot read Arabic.



The root cause is simple:



> \*\*Image generators treat Arabic script as visual texture,

> not as linguistic structure.\*\*



This is not a data problem. It is not a model size problem.

It is a category error. You cannot fix it by training on more

Arabic images. You can only fix it by changing which system is

responsible for writing the letters.



\---



\## The Solution — The Inversion Principle



Current systems:

Prompt → Diffusion model → (attempt) Arabic text



Khatt Engine:

Arabic text → Linguistic engine → Geometric skeleton →

Diffusion model → Stylized image



The inversion is total. Arabic writing is removed from the

diffusion model's responsibilities entirely. A deterministic

system that cannot hallucinate generates the letterforms.

The AI receives a pre-written, geometrically correct skeleton

and is only permitted to decide what the ink looks like.



\---



\## Architecture — Five Layers

┌─────────────────────────────────────────────┐

│  INPUT: Arabic Unicode text + style name    │

└─────────────────────┬───────────────────────┘

│

╔═════════════▼═════════════════╗

║   DETERMINISTIC ZONE          ║

║   No hallucination possible   ║

║                               ║

║  Layer 1 — Linguistic engine  ║

║  HarfBuzz + FreeType          ║

║  Resolves every glyph into    ║

║  its correct contextual form  ║

║                               ║

║  Layer 2 — Skeleton renderer  ║

║  Converts glyph outlines to   ║

║  pixel-precise black on white ║

║  with dot-boost enforcement   ║

║                               ║

║  Layer 3 — Control encoder    ║

║  Enforces aspect ratio,       ║

║  prepares skeleton for API    ║

╚═════════════╤═════════════════╝

│

╔═════════════▼═════════════════╗

║   AI ZONE                     ║

║   Painting only, not writing  ║

║                               ║

║  Layer 4 — Style diffusion    ║

║  Stability AI sketch API      ║

║  Applies ink, paper, texture  ║

║  Cannot invent letterforms    ║

║                               ║

║  Layer 5 — Validation gate    ║

║  Arabic OCR checks skeleton   ║

║  Rejects linguistically       ║

║  invalid output               ║

╚═════════════╤═════════════════╝

│

┌─────────────────────▼───────────────────────┐

│  OUTPUT: Verified calligraphic image        │

└─────────────────────────────────────────────┘



\### Layer 1 — Linguistic Engine



Built on \*\*HarfBuzz\*\*, the same open-source shaping engine

inside Chrome, Firefox, and LibreOffice.



HarfBuzz resolves every Arabic joining rule, every contextual

form substitution, every ligature. The input ب ي ت becomes

the correctly shaped, contextually aware glyph sequence for

بيت — initial ba, medial ya, final ta — not three isolated

letters placed next to each other.



This layer produces zero probability distributions. Its output

is deterministic and auditable.



\### Layer 2 — Skeleton Renderer



Built on \*\*FreeType\*\*, which extracts the Bézier outline of

each glyph from the font file and rasterizes it to a pixel

array using NumPy for performance.



The renderer includes \*\*dot boost\*\* — a post-processing step

that identifies small isolated ink regions (dots and diacritics)

and slightly enlarges them before sending to the AI. This

prevents the AI from treating dots as noise and ignoring them,

which would corrupt the linguistic content of the output.



Without dot boost: the AI removes dots, changing ب to a

different letter entirely.

With dot boost: the AI treats dots as part of the composition

and renders them with the same ink quality as the letter bodies.



\### Layer 3 — Control Signal Encoder



Prepares the skeleton for transmission to the AI:



\- Enforces Stability AI's aspect ratio requirement (max 2.4:1)

\- Scales to 1024px width for optimal AI input resolution

\- Pads with white space rather than cropping content



\### Layer 4 — Style Diffusion Core



Uses the \*\*Stability AI sketch control endpoint\*\*, which accepts

a line-art image and a style prompt and produces a photorealistic

rendering that follows the structural geometry of the input.



The sketch endpoint was chosen over the structure endpoint

because our skeleton is line art — clean black strokes on white —

not a depth map or 3D scene. The sketch endpoint is specifically

calibrated for this input type.



Each calligraphic style has a dedicated prompt engineered to

produce the correct historical aesthetic without overriding the

skeleton geometry.



\### Layer 5 — Validation Gate



Uses \*\*EasyOCR\*\* with Arabic language models to read text from

the skeleton image and compare it to the input using Levenshtein

distance on sorted character sets.



Current limitation: OCR is run against the skeleton, not the

stylized output, because no publicly available OCR model is

trained on calligraphic hands. Calligraphic OCR is the primary

research task for Phase 6 of the roadmap.



\---



\## Supported Styles



| Style | Font | Character |

|---|---|---|

| Thuluth ثلث | Amiri | Black ink, aged parchment, classical |

| Naskh نسخ | Amiri | Clean, legible, white paper |

| Diwani ديواني | Amiri | Gold ink, Ottoman court style |

| Nastaliq نستعليق | Noto Nastaliq Urdu | Diagonal, Persian manuscript |

| Ruqah رقعة | Aref Ruqaa | Compressed, everyday script |

| Kufic كوفي | Reem Kufi | Angular, geometric, monumental |



\*\*Important:\*\* Thuluth, Naskh, and Diwani share the Amiri font

and therefore produce identical skeleton geometry. The visual

difference between them is currently produced by prompt

engineering only. True structural differentiation requires

dedicated OpenType fonts for each style — a commissioning task

planned for Phase 3 of the roadmap.



Nastaliq, Ruqah, and Kufic use structurally distinct fonts and

produce genuinely different letterform geometry at the skeleton

level.



\---



\## Installation



\### Requirements



\- Python 3.11+

\- Windows, macOS, or Linux

\- Stability AI API key (free tier available)

\- Internet connection for stylization (all other layers run locally)



\### Setup



```bash

git clone https://github.com/your-username/khatt-engine

cd khatt-engine

uv venv

source .venv/bin/activate  # Windows: .venv\\Scripts\\activate

uv pip install -e .

```



\### Font installation



Download these four fonts and place them in `assets/fonts/`:



| File | Source |

|---|---|

| `Amiri-Regular.ttf` | github.com/aliftype/amiri |

| `NotoNastaliqUrdu-Regular.ttf` | fonts.google.com |

| `ArefRuqaa-Regular.ttf` | fonts.google.com |

| `ReemKufi-Regular.ttf` | fonts.google.com |



\### API key



Create a `.env` file in the project root:

STABILITY\_API\_KEY=sk-your-key-here



\---



\## Usage



\### Command line



```bash

python -m khatt "بسم الله" --style thuluth

python -m khatt "الرحمن الرحيم" --style nastaliq

python -m khatt "الله" --style kufic

```



\### Web interface



```bash

uvicorn khatt.api.server:app --reload --host 0.0.0.0 --port 8000

```



Open `http://localhost:8000` in your browser.



\### Python API



```python

from khatt.pipeline import run

run("بسم الله", style="thuluth")

```



\---



\## Project Structure

khatt-engine/

├── src/khatt/

│   ├── linguistic/

│   │   └── shaper.py          # HarfBuzz text shaping

│   ├── geometry/

│   │   └── skeleton.py        # FreeType skeleton renderer

│   ├── diffusion/

│   │   └── stylizer.py        # Stability AI integration

│   ├── validation/

│   │   └── gate.py            # Arabic OCR validation

│   ├── api/

│   │   └── server.py          # FastAPI REST server

│   ├── web/

│   │   └── index.html         # Browser interface

│   ├── pipeline.py            # Unified five-layer pipeline

│   └── main.py            # CLI entry point

├── assets/

│   └── fonts/                 # Arabic OpenType fonts

├── outputs/                   # Generated images

├── .env                       # API keys (not committed)

└── pyproject.toml



\---



\## Roadmap



\### Phase 1 — MVP (complete)

\- HarfBuzz linguistic shaping

\- FreeType skeleton rendering

\- Stability AI stylization via sketch control

\- OCR validation gate

\- CLI and browser interface

\- Six calligraphic styles

\- Dot boost for diacritic preservation



\### Phase 2 — Quality (current)

\- Prompt engineering refinement per style

\- Dot composite fallback system

\- Aspect ratio enforcement

\- Multi-font structural diversity



\### Phase 3 — Font commissioning

\- Commission dedicated OpenType fonts for Thuluth and Diwani

\- True structural differentiation between all six styles

\- Ibn al-Muqla proportion engine integration



\### Phase 4 — API and deployment

\- Public REST API with rate limiting

\- Docker containerization

\- Cloud deployment



\### Phase 5 — Multi-generator support

\- DALL-E 3 image-to-image adapter

\- Midjourney reference image adapter

\- Adobe Firefly inpainting adapter



\### Phase 6 — LoRA training (research)

\- Assemble dataset of 50,000+ labeled calligraphic images

\- Train Arabic calligraphic OCR model

\- Fine-tune LoRA on museum-digitized works

\- Replace prompt-based stylization with trained model



\---



\## The Core Insight



The gap between the current broken state and the correct state

is not a gap in AI capability. It is a gap in AI responsibility.



Current systems ask the AI to do something it was never designed

to do — write a linguistically structured script from scratch.

This architecture reassigns responsibilities correctly:



\- \*\*Language\*\* goes to language tools (HarfBuzz)

\- \*\*Geometry\*\* goes to geometric tools (FreeType)

\- \*\*Aesthetics\*\* goes to the AI (Stability AI)



By doing so, the gap closes entirely.



\---



\## License



MIT License. See LICENSE file.



\---



\## Acknowledgments



\- \*\*HarfBuzz\*\* — text shaping engine by Behdad Esfahbod

\- \*\*Amiri\*\* — Arabic typeface by Khaled Hosny

\- \*\*Noto Nastaliq Urdu\*\* — Google Fonts

\- \*\*Aref Ruqaa\*\* — Google Fonts  

\- \*\*Reem Kufi\*\* — Google Fonts

\- \*\*Stability AI\*\* — image generation API

\- \*\*EasyOCR\*\* — OCR engine by JaidedAI

