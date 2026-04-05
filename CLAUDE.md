# autodex-gallery

Web gallery for AutoDex grasp candidates and experiment results.

## Repository Structure

```
autodex-gallery/
├── CLAUDE.md
├── docs/                          # GitHub Pages (static site)
│   ├── index.html                 # Landing page (Gallery / Experiments)
│   ├── gallery.html               # Object thumbnail grid
│   ├── object.html                # Object detail: hand tabs + turntable videos
│   ├── experiments.html           # Experiment videos (placeholder)
│   ├── catalog.json               # Object metadata (id, name, hands, thumbnail)
│   ├── css/style.css              # Shared styles (dark theme)
│   ├── js/                        # (future JS modules)
│   └── objects/{name}/thumb.png   # Thumbnails (committed to git)
├── scripts/
│   └── upload_turntable.py        # Upload turntable MP4s to HuggingFace
└── .github/workflows/deploy.yml   # Auto-deploy to GitHub Pages on push
```

## Data Flow

1. **Turntable videos** rendered by `AutoDex/src/visualization/turntable_grasp.py` → `AutoDex/data/{hand}/{obj}/{rank}/turntable.mp4`
2. **Upload to HuggingFace**: `python scripts/upload_turntable.py`
3. **Website loads videos** from HuggingFace: `https://huggingface.co/datasets/willi19/autodex-gallery/resolve/main/turntable/{hand}/{obj}/{rank}/turntable.mp4`
4. **Thumbnails** reused from `object_processing/docs/objects/{name}/thumb.png` (committed to git, served locally)

## What is stored where

| Asset | Location | Why |
|-------|----------|-----|
| Turntable MP4s | HuggingFace `willi19/autodex-gallery` | Large files (~2.9GB total) |
| Object thumbnails | GitHub `docs/objects/{name}/thumb.png` | Small PNGs (~6KB each) |
| HTML/CSS/JS | GitHub `docs/` | Static site via GitHub Pages |
| catalog.json | GitHub `docs/catalog.json` | Object metadata |
| Experiment videos | HuggingFace (TBD) | Large files |

## Navigation

```
Landing (index.html)
├── Gallery (gallery.html)
│   └── Object grid (searchable)
│       └── Object detail (object.html?obj=...)
│           ├── [Allegro | Inspire] tabs
│           └── Turntable video grid (setcover rank order)
└── Experiments (experiments.html)
    └── (TBD: experiment list → video player with camera selection)
```

## HuggingFace Dataset Structure

```
willi19/autodex-gallery/
├── turntable/
│   ├── allegro/{obj_name}/{rank:03d}/turntable.mp4
│   └── inspire/{obj_name}/{rank:03d}/turntable.mp4
└── experiments/   (TBD)
```

## Key Details

- **100 objects** total, 100 allegro + 96 inspire
- **~18,200 turntable videos**, ~150KB each
- **GitHub Actions**: auto-deploys `docs/` to Pages on push to `main`
- **Dark theme** UI, responsive grid layout
- **No build step**: pure static HTML/JS, no bundler

## Commands

```bash
# Upload turntable videos to HuggingFace
python scripts/upload_turntable.py                    # All
python scripts/upload_turntable.py --hand allegro     # One hand
python scripts/upload_turntable.py --obj apple        # One object
python scripts/upload_turntable.py --dry-run          # Preview

# Update catalog.json (after adding new objects)
# Run from AutoDex repo, copy result here
```

## Adding Experiment Videos

When experiments are ready:
1. Create `experiments.json` in `docs/` with experiment metadata
2. Upload experiment videos to HuggingFace under `experiments/`
3. Update `experiments.html` to load from `experiments.json`
4. Experiment detail page: camera serial selector + merged view
