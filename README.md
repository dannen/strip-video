# strip-video

A Python video effect that slices footage into strips and animates them with sinusoidal offsets — replicating the shredder/strip aesthetic seen in Placebo music videos.

Each strip gets an independently randomised waveform (sine, triangle, soft-square, or sawtooth) and frequency so their motion is genuinely out of sync. The effect alternates between horizontal strips sliding left/right and vertical strips sliding up/down on a canvas 35% larger than the source, with strips overshooting the canvas edges by up to 40%. Each strip renders with a drop shadow and a subtle separation gap that rises then slowly decays over the video. Optional static hold at the start and end bookends the effect, with configurable ease-in and ease-out ramps. At each lr↔ud transition, all strips converge to zero offset before diverging in the new direction.

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
# Default settings — black background, both modes alternating every 8s
uv run python3 strip_video.py input.mp4 output.mp4

# Cycle background through colours (snaps between colours, no fade)
uv run python3 strip_video.py input.mp4 output.mp4 --bg cycle

# Passing --colors implies --bg cycle automatically
uv run python3 strip_video.py input.mp4 output.mp4 --colors red hotpink cyan

# Cycle with fade in/out through black between colours
uv run python3 strip_video.py input.mp4 output.mp4 --bg cycle --color-fade

# Earth/red tone palette with fade
uv run python3 strip_video.py input.mp4 output.mp4 --color-fade \
  --colors brown saddlebrown sienna chocolate peru tomato darkred

# Hex colours
uv run python3 strip_video.py input.mp4 output.mp4 \
  --colors "#8B0000" "#A0522D" "#D2691E" "#CD853F"

# Left-right strips only
uv run python3 strip_video.py input.mp4 output.mp4 --mode lr

# Up-down strips only
uv run python3 strip_video.py input.mp4 output.mp4 --mode ud

# No drop shadow, no strip separation
uv run python3 strip_video.py input.mp4 output.mp4 --shadow-x 0 --shadow-y 0 --strip-sep 0

# 6-second static hold at start and end, 3-second ease-in/out
uv run python3 strip_video.py input.mp4 output.mp4 --static-begin 6 --static-end 6
```

## Options

### Strip motion

| Flag | Default | Description |
|---|---|---|
| `--mode` | `both` | `lr` = horizontal strips only, `ud` = vertical only, `both` = alternate |
| `--n-lr` | `9` | Number of horizontal strips (left-right phase) |
| `--n-ud` | `16` | Number of vertical strips (up-down phase) |
| `--freq` | `0.042` | Base oscillation frequency in Hz (~24s per cycle) |
| `--freq-spread` | `0.35` | Per-strip frequency variation (±35% of base freq) |
| `--phase-gap` | `π` | Phase offset between adjacent strips — π = maximum anti-phase |
| `--max-speed` | `0` | Max strip velocity in px/s (0 = auto: scales with amplitude × freq) |
| `--edge-margin` | `0.0` | How far short of the travel limit strips stop (0 = reach limit, 0.2 = 20% short) |
| `--random-margin` | `0.05` | Max extra random margin re-rolled per strip each oscillation cycle |
| `--seed` | `42` | RNG seed for per-strip randomisation |

### Canvas & edges

| Flag | Default | Description |
|---|---|---|
| `--canvas-expand` | `0.35` | Fractional canvas expansion (0.35 = 35% larger each dimension) |
| `--overshoot` | `0.4` | How far past the canvas edge strips travel, as a fraction of frame size |

### Visual effects

| Flag | Default | Description |
|---|---|---|
| `--shadow-x` | `4` | Drop shadow offset rightward in pixels (0 = disabled) |
| `--shadow-y` | `4` | Drop shadow offset downward in pixels (0 = disabled) |
| `--strip-sep` | `4.0` | Peak gap between strips in pixels — rises to peak at ~20% through video, decays to 0 by end |
| `--fade-frames` | `24` | Frames to fade video to black at each mode switch (0 = disabled) |

### Background

| Flag | Default | Description |
|---|---|---|
| `--bg` | `black` | Background: named colour, `#RRGGBB`, or `cycle` |
| `--colors` | `red hotpink cyan yellow lime white black` | Colours to cycle through — passing this flag implies `--bg cycle` |
| `--color-hold` | `8.0` | Seconds each colour is held at full brightness (cycle mode) |
| `--color-fade` | _(off)_ | Enable fade in/out through black between colours (cycle mode) |
| `--color-fade-secs` | `4.0` | Fade duration in seconds (requires `--color-fade`) |

### Static hold & ramps

| Flag | Default | Description |
|---|---|---|
| `--static-begin` | `0.0` | Seconds of unaltered video at the start before strips engage |
| `--static-end` | `0.0` | Seconds of unaltered video at the end after strips disengage |
| `--ramp-begin` | `3.0` | Seconds to ease-in strip amplitude after static-begin (cosine curve, 0 = instant) |
| `--ramp-end` | `3.0` | Seconds to ease-out strip amplitude before static-end (cosine curve, 0 = instant) |

### Mode transitions

| Flag | Default | Description |
|---|---|---|
| `--interval` | `14.0` | Seconds between lr ↔ ud alternations in `both` mode (0 = single transition) |
| `--transition-secs` | `2.5` | Crossfade duration between modes; strips converge to zero offset at each boundary |
| `--transition-at` | `0.5` | Fraction of video for single transition (interval=0 only) |
| `--transition-width` | `0.04` | Crossfade width as fraction of total duration (interval=0 only) |

### Named colours

All CSS named colours are supported — neutrals, reds, browns, oranges, greens, blues, purples, and cyans. Some useful ones:

`red` `hotpink` `deeppink` `coral` `tomato` `orange` `gold` `yellow` `lime` `cyan` `teal` `dodgerblue` `blue` `mediumpurple` `magenta` `white` `black`

Some warm/earth tones:

`brown` `saddlebrown` `sienna` `chocolate` `peru` `sandybrown` `tan` `burlywood` `rosybrown` `orangered` `darkorange` `goldenrod`
