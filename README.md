# strip-video

A Python video effect that slices footage into strips and animates them with sinusoidal offsets — replicating the shredder/strip aesthetic seen in Placebo music videos.

Each strip gets an independently randomised waveform (sine, triangle, soft-square, or sawtooth) and frequency, so their motion is genuinely out of sync. The canvas background cycles through colours with smooth black fades between them. The effect alternates between horizontal strips sliding left/right and vertical strips sliding up/down.

## Requirements

- [uv](https://github.com/astral-sh/uv)
- ffmpeg (for audio extraction/muxing)

## Install

```bash
git clone https://github.com/jher23/strip-video
cd strip-video
uv sync
```

## Usage

```bash
uv run python3 strip_video.py input.mp4 output.mp4 [options]
```

### Examples

```bash
# Default settings — black background, both modes alternating every 6s
uv run python3 strip_video.py input.mp4 output.mp4

# Cycle through primary colours
uv run python3 strip_video.py input.mp4 output.mp4 --bg cycle

# Earth/red tone palette
uv run python3 strip_video.py input.mp4 output.mp4 --bg cycle \
  --colors brown saddlebrown sienna chocolate peru tomato darkred

# Hex colours
uv run python3 strip_video.py input.mp4 output.mp4 --bg cycle \
  --colors "#8B0000" "#A0522D" "#D2691E" "#CD853F"

# Left-right strips only
uv run python3 strip_video.py input.mp4 output.mp4 --mode lr

# Up-down strips only
uv run python3 strip_video.py input.mp4 output.mp4 --mode ud
```

## Options

| Flag | Default | Description |
|---|---|---|
| `--mode` | `both` | `lr` = horizontal strips only, `ud` = vertical only, `both` = alternate |
| `--n-lr` | `16` | Number of horizontal strips (left-right phase) |
| `--n-ud` | `9` | Number of vertical strips (up-down phase) |
| `--edge-margin` | `0.1` | How far short of the canvas edge strips stop (0 = touch edge, 0.2 = 20% short) |
| `--random-margin` | `0.05` | Max extra random margin re-rolled per strip each oscillation cycle |
| `--freq` | `0.3` | Base oscillation frequency in Hz |
| `--freq-spread` | `0.35` | Per-strip frequency variation (±35% of base freq) |
| `--phase-gap` | `π` | Phase offset between adjacent strips — π = maximum anti-phase |
| `--max-speed` | `25` | Max strip velocity in px/s (0 = auto) |
| `--seed` | `42` | RNG seed for per-strip randomisation |
| `--canvas-expand` | `0.2` | Fractional canvas expansion (0.2 = 20% larger) |
| `--bg` | `black` | Background: named colour, `#RRGGBB`, or `cycle` |
| `--colors` | `red green blue white black` | Colours to cycle through with `--bg cycle` |
| `--color-hold` | `8.0` | Seconds each colour is held at full brightness (cycle mode) |
| `--color-fade` | `4.0` | Seconds to fade in/out through black (cycle mode) |
| `--interval` | `6.0` | Seconds between lr ↔ ud alternations in `both` mode (0 = single transition) |
| `--transition-secs` | `0.5` | Crossfade duration between modes |
| `--fade-frames` | `24` | Frames to fade video strips to black at each mode switch (0 = disabled) |
| `--transition-at` | `0.5` | Fraction of video for single transition (interval=0 only) |
| `--transition-width` | `0.04` | Crossfade width as fraction of total duration (interval=0 only) |

### Named colours

All CSS named colours are supported — neutrals, reds, browns, oranges, greens, blues, purples, and cyans. Some useful ones for warm/earth palettes:

`brown` `saddlebrown` `sienna` `chocolate` `peru` `sandybrown` `tan` `burlywood` `rosybrown` `tomato` `coral` `salmon` `orangered` `darkorange` `gold` `goldenrod`
