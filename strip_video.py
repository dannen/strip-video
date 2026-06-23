#!/usr/bin/env python3
"""
Strip video effect — replicates the Placebo shredder/strip effect.

Strips each get a randomised waveform (sine, triangle, soft-square, sawtooth)
and a randomised frequency so their motion is genuinely independent.

Travel distance is controlled by --edge-margin (0 = reach canvas edge,
0.2 = stop 20% short). Each strip also rolls a small random extra margin
after every full oscillation cycle so they don't all hit the limit together.
Strips never pass the canvas edge.

Background cycles: black → color → black → next color, with configurable
hold and fade durations.

Modes:
  lr   — horizontal strips shifting left/right only
  ud   — vertical strips shifting up/down only
  both — transition from lr to ud mid-video (default)
"""

import argparse
import math
import os
import subprocess
import sys
import tempfile

import cv2
import numpy as np


def _rgb(r, g, b):
    return (b, g, r)   # store as BGR for OpenCV


# CSS-compatible named colors. Hex equivalents work too: #RRGGBB
NAMED_COLORS = {
    # Neutrals
    "black":          _rgb(0,   0,   0),
    "white":          _rgb(255, 255, 255),
    "gray":           _rgb(128, 128, 128),
    "grey":           _rgb(128, 128, 128),
    "silver":         _rgb(192, 192, 192),
    "darkgray":       _rgb(169, 169, 169),
    "lightgray":      _rgb(211, 211, 211),
    # Reds / pinks
    "red":            _rgb(255, 0,   0),
    "darkred":        _rgb(139, 0,   0),
    "maroon":         _rgb(128, 0,   0),
    "crimson":        _rgb(220, 20,  60),
    "firebrick":      _rgb(178, 34,  34),
    "tomato":         _rgb(255, 99,  71),
    "coral":          _rgb(255, 127, 80),
    "salmon":         _rgb(250, 128, 114),
    "lightsalmon":    _rgb(255, 160, 122),
    "orangered":      _rgb(255, 69,  0),
    "hotpink":        _rgb(255, 105, 180),
    "deeppink":       _rgb(255, 20,  147),
    "pink":           _rgb(255, 192, 203),
    # Browns / earth tones
    "brown":          _rgb(165, 42,  42),
    "saddlebrown":    _rgb(139, 69,  19),
    "sienna":         _rgb(160, 82,  45),
    "chocolate":      _rgb(210, 105, 30),
    "peru":           _rgb(205, 133, 63),
    "sandybrown":     _rgb(244, 164, 96),
    "tan":            _rgb(210, 180, 140),
    "burlywood":      _rgb(222, 184, 135),
    "wheat":          _rgb(245, 222, 179),
    "rosybrown":      _rgb(188, 143, 143),
    # Oranges / golds
    "orange":         _rgb(255, 165, 0),
    "darkorange":     _rgb(255, 140, 0),
    "gold":           _rgb(255, 215, 0),
    "goldenrod":      _rgb(218, 165, 32),
    "darkgoldenrod":  _rgb(184, 134, 11),
    "khaki":          _rgb(240, 230, 140),
    "darkkhaki":      _rgb(189, 183, 107),
    # Greens
    "green":          _rgb(0,   128, 0),
    "lime":           _rgb(0,   255, 0),
    "darkgreen":      _rgb(0,   100, 0),
    "forestgreen":    _rgb(34,  139, 34),
    "limegreen":      _rgb(50,  205, 50),
    "seagreen":       _rgb(46,  139, 87),
    "mediumseagreen": _rgb(60,  179, 113),
    "springgreen":    _rgb(0,   255, 127),
    "olive":          _rgb(128, 128, 0),
    "darkolivegreen": _rgb(85,  107, 47),
    "olivedrab":      _rgb(107, 142, 35),
    "yellowgreen":    _rgb(154, 205, 50),
    "chartreuse":     _rgb(127, 255, 0),
    "aquamarine":     _rgb(127, 255, 212),
    "turquoise":      _rgb(64,  224, 208),
    "darkturquoise":  _rgb(0,   206, 209),
    "teal":           _rgb(0,   128, 128),
    "cadetblue":      _rgb(95,  158, 160),
    # Blues
    "blue":           _rgb(0,   0,   255),
    "navy":           _rgb(0,   0,   128),
    "darkblue":       _rgb(0,   0,   139),
    "mediumblue":     _rgb(0,   0,   205),
    "royalblue":      _rgb(65,  105, 225),
    "steelblue":      _rgb(70,  130, 180),
    "dodgerblue":     _rgb(30,  144, 255),
    "deepskyblue":    _rgb(0,   191, 255),
    "skyblue":        _rgb(135, 206, 235),
    "lightblue":      _rgb(173, 216, 230),
    "cornflowerblue": _rgb(100, 149, 237),
    "midnightblue":   _rgb(25,  25,  112),
    # Purples / violets
    "purple":         _rgb(128, 0,   128),
    "indigo":         _rgb(75,  0,   130),
    "violet":         _rgb(238, 130, 238),
    "magenta":        _rgb(255, 0,   255),
    "fuchsia":        _rgb(255, 0,   255),
    "plum":           _rgb(221, 160, 221),
    "orchid":         _rgb(218, 112, 214),
    "mediumorchid":   _rgb(186, 85,  211),
    "mediumpurple":   _rgb(147, 112, 219),
    "slateblue":      _rgb(106, 90,  205),
    "darkviolet":     _rgb(148, 0,   211),
    "darkorchid":     _rgb(153, 50,  204),
    # Cyans / teals
    "cyan":           _rgb(0,   255, 255),
    "aqua":           _rgb(0,   255, 255),
    "lightcyan":      _rgb(224, 255, 255),
    "paleturquoise":  _rgb(175, 238, 238),
    # Yellows
    "yellow":         _rgb(255, 255, 0),
    "lightyellow":    _rgb(255, 255, 224),
    "lemonchiffon":   _rgb(255, 250, 205),
}

DEFAULT_CYCLE_COLORS = ["red", "hotpink", "cyan", "yellow", "lime", "white", "black"]


def parse_color(s):
    """Parse a named color or #RRGGBB hex string into a BGR tuple.
    Returns the string 'cycle' unchanged."""
    if s.lower() == "cycle":
        return "cycle"
    if s.lower() in NAMED_COLORS:
        return NAMED_COLORS[s.lower()]
    h = s.lstrip("#")
    if len(h) == 6:
        try:
            r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
            return (b, g, r)
        except ValueError:
            pass
    known = ", ".join(sorted(NAMED_COLORS))
    raise ValueError(f"Unknown color: {s!r}\nNamed colors: {known}\nOr use #RRGGBB hex.")


def smooth_cycle_color(t, hold, fade, colors):
    """black → color (fade in) → hold → black (fade out) → next color …
    colors: list of BGR tuples."""
    cycle_len = 2 * fade + hold
    color_idx = int(t / cycle_len) % len(colors)
    phase = t % cycle_len
    color = colors[color_idx]
    if phase < fade:
        alpha = phase / fade
    elif phase < fade + hold:
        alpha = 1.0
    else:
        alpha = 1.0 - (phase - fade - hold) / fade
    return tuple(int(c * alpha) for c in color)


# ---------------------------------------------------------------------------
# Per-strip randomised motion
# ---------------------------------------------------------------------------

WAVEFORM_NAMES = ["sine", "triangle", "soft_square", "sawtooth"]


def _wave(name, x):
    if name == "sine":
        return math.sin(x)
    elif name == "triangle":
        return 2.0 / math.pi * math.asin(max(-1.0, min(1.0, math.sin(x))))
    elif name == "soft_square":
        return math.tanh(3.0 * math.sin(x))
    else:  # sawtooth
        return 2.0 * ((x / (2 * math.pi)) % 1.0) - 1.0


def build_strip_params(n_strips, freq_spread, seed):
    """Returns list of (freq_scale, waveform_name, extra_phase) per strip.

    Phases are stratified: [0, 2π] is divided into n_strips equal bins and one
    sample is drawn from each bin before shuffling. This guarantees that no two
    strips share a phase bucket, preventing the visible clustering that occurs
    when purely random phases happen to land near each other.
    """
    rng = np.random.default_rng(seed)
    # Stratified phase: one sample per bin, shuffled for strip assignment
    bin_size = 2 * math.pi / n_strips
    phase_offsets = (np.arange(n_strips) * bin_size
                     + rng.uniform(0.0, bin_size, n_strips)) % (2 * math.pi)
    rng.shuffle(phase_offsets)
    params = []
    for i in range(n_strips):
        freq_scale = float(rng.uniform(1.0 - freq_spread, 1.0 + freq_spread))
        waveform = WAVEFORM_NAMES[int(rng.integers(0, len(WAVEFORM_NAMES)))]
        params.append((freq_scale, waveform, float(phase_offsets[i])))
    return params


def compute_waves(n, t, base_freq, phase_gap, params):
    """Raw waveform values in [-1, 1] per strip (before amplitude scaling)."""
    waves = []
    for i in range(n):
        freq_scale, waveform, extra_phase = params[i]
        x = 2 * math.pi * base_freq * freq_scale * t + i * phase_gap + extra_phase
        waves.append(_wave(waveform, x))
    return waves


def speed_limit(desired, current, max_delta, clamp_abs):
    """
    Move each strip toward its desired position by at most max_delta pixels,
    then hard-clamp to [-clamp_abs, clamp_abs] so strips never pass the edge.
    """
    result = []
    for d, c in zip(desired, current):
        delta = d - c
        if abs(delta) > max_delta:
            delta = math.copysign(max_delta, delta)
        new_pos = c + delta
        result.append(max(-clamp_abs, min(clamp_abs, new_pos)))
    return result


def update_margins(waves, prev_waves, half_cycles, extra_margins, random_margin, rng):
    """
    Detect zero crossings (half-cycles). After two crossings (one full cycle)
    re-roll each strip's random extra margin.
    Mutates half_cycles and extra_margins in place; updates prev_waves list.
    """
    for i in range(len(waves)):
        if prev_waves[i] * waves[i] < 0:          # sign change = zero crossing
            half_cycles[i] += 1
            if half_cycles[i] >= 2:                # full cycle complete
                extra_margins[i] = float(rng.uniform(0.0, random_margin))
                half_cycles[i] = 0
        prev_waves[i] = waves[i]


# ---------------------------------------------------------------------------
# Frame renderers (accept pre-computed float offsets)
# ---------------------------------------------------------------------------

def apply_lr(frame, n_strips, offsets, bg, pad_x, pad_y, shadow_x=0, shadow_y=0, sep=0.0, shadow_color=(0, 0, 0)):
    """Horizontal strips shifted left/right on expanded canvas."""
    h, w = frame.shape[:2]
    H_out, W_out = h + 2 * pad_y, w + 2 * pad_x
    canvas = np.full((H_out, W_out, 3), bg, dtype=np.uint8)
    strip_h = h // n_strips
    center = (n_strips - 1) / 2.0

    for i in range(n_strips):
        y0 = i * strip_h
        y1 = y0 + strip_h if i < n_strips - 1 else h
        strip = frame[y0:y1]
        sh = y1 - y0
        off = int(offsets[i])
        sep_off = int(round((i - center) * sep))

        cx = pad_x + off
        cy = pad_y + y0 + sep_off

        if shadow_x or shadow_y:
            bx0 = max(0, cx + shadow_x)
            bx1 = min(W_out, cx + shadow_x + w)
            by0 = max(0, cy + shadow_y)
            by1 = min(H_out, cy + shadow_y + sh)
            if bx1 > bx0 and by1 > by0:
                canvas[by0:by1, bx0:bx1] = shadow_color

        src_x0 = max(0, -cx);  dst_x0 = max(0, cx);  src_x1 = min(w, W_out - cx)
        src_y0 = max(0, -cy);  dst_y0 = max(0, cy);  src_y1 = min(sh, H_out - cy)
        if src_x1 > src_x0 and dst_x0 < W_out and src_y1 > src_y0 and dst_y0 < H_out:
            canvas[dst_y0:dst_y0 + (src_y1 - src_y0),
                   dst_x0:dst_x0 + (src_x1 - src_x0)] = strip[src_y0:src_y1, src_x0:src_x1]

    return canvas


def apply_ud(frame, n_strips, offsets, bg, pad_x, pad_y, shadow_x=0, shadow_y=0, sep=0.0, shadow_color=(0, 0, 0)):
    """Vertical strips shifted up/down on expanded canvas."""
    h, w = frame.shape[:2]
    H_out, W_out = h + 2 * pad_y, w + 2 * pad_x
    canvas = np.full((H_out, W_out, 3), bg, dtype=np.uint8)
    strip_w = w // n_strips
    center = (n_strips - 1) / 2.0

    for i in range(n_strips):
        x0 = i * strip_w
        x1 = x0 + strip_w if i < n_strips - 1 else w
        strip = frame[:, x0:x1]
        sw = x1 - x0
        off = int(offsets[i])
        sep_off = int(round((i - center) * sep))

        cx = pad_x + x0 + sep_off
        cy = pad_y + off

        if shadow_x or shadow_y:
            bx0 = max(0, cx + shadow_x)
            bx1 = min(W_out, cx + shadow_x + sw)
            by0 = max(0, cy + shadow_y)
            by1 = min(H_out, cy + shadow_y + h)
            if bx1 > bx0 and by1 > by0:
                canvas[by0:by1, bx0:bx1] = shadow_color

        src_x0 = max(0, -cx);  dst_x0 = max(0, cx);  src_x1 = min(sw, W_out - cx)
        src_y0 = max(0, -cy);  dst_y0 = max(0, cy);  src_y1 = min(h, H_out - cy)
        if src_x1 > src_x0 and dst_x0 < W_out and src_y1 > src_y0 and dst_y0 < H_out:
            canvas[dst_y0:dst_y0 + (src_y1 - src_y0),
                   dst_x0:dst_x0 + (src_x1 - src_x0)] = strip[src_y0:src_y1, src_x0:src_x1]

    return canvas


def strip_sep_value(progress, peak_sep, peak_at=0.2):
    """Rises linearly to peak_sep at peak_at, then decays linearly to 0 by end."""
    if progress <= peak_at:
        return peak_sep * (progress / peak_at)
    return peak_sep * (1.0 - (progress - peak_at) / max(1.0 - peak_at, 1e-9))


def blend_frames(a, b, alpha):
    return cv2.addWeighted(a, 1.0 - alpha, b, alpha, 0)


def ramp_in_factor(t, t_start, ramp_secs):
    """Cosine ease-in from 0→1 over ramp_secs after t_start."""
    if ramp_secs <= 0:
        return 1.0
    elapsed = t - t_start
    if elapsed <= 0:
        return 0.0
    if elapsed >= ramp_secs:
        return 1.0
    return (1.0 - math.cos(math.pi * elapsed / ramp_secs)) / 2.0


def ramp_out_factor(t, t_end, ramp_secs):
    """Cosine ease-out from 1→0 over ramp_secs before t_end."""
    if ramp_secs <= 0:
        return 1.0
    remaining = t_end - t
    if remaining <= 0:
        return 0.0
    if remaining >= ramp_secs:
        return 1.0
    return (1.0 - math.cos(math.pi * remaining / ramp_secs)) / 2.0


def align_factor(t, interval, transition_secs):
    """
    1.0 normally; eases to 0 at each mode-switch boundary via cosine curve so
    strips converge to zero offset/gap right at the transition, then diverge.
    Cosine ease means the motion starts and ends slowly — no abrupt jerk.
    """
    if interval <= 0 or transition_secs <= 0:
        return 1.0
    half = transition_secs / 2.0
    boundary_n = round(t / interval)
    if boundary_n == 0:
        return 1.0
    dist = abs(t - boundary_n * interval)
    if dist >= half:
        return 1.0
    return (1.0 - math.cos(math.pi * dist / half)) / 2.0


def fade_factor(t, interval, transition_at, total_secs, fade_frames, fps):
    """
    Returns a brightness multiplier in [0, 1] centered on each mode-switch boundary.
    0 = full black at the boundary, 1 = full brightness away from it.
    Uses a cosine ease so the fade feels cinematic rather than linear.
    """
    if fade_frames <= 0:
        return 1.0
    half_window = (fade_frames / 2.0) / fps

    if interval > 0:
        # Repeating boundaries at t = interval, 2*interval, … (skip t=0)
        boundary_n = round(t / interval)
        if boundary_n == 0:
            return 1.0
        dist = abs(t - boundary_n * interval)
    else:
        # Single transition
        dist = abs(t - transition_at * total_secs)

    if dist >= half_window:
        return 1.0
    # Power curve (exponent < 1): brightness drops slowly from full,
    # touches black briefly at center, recovers gradually — feels like a dimmer
    return (dist / half_window) ** 0.4


def alpha_for_interval(t, interval):
    """
    Returns mode alpha (0=lr, 1=ud) for repeating interval mode — hard cut only.
    Strip positions are already converged to zero at each boundary by align_factor,
    so the cut is invisible; blending is not needed and creates ghost overlays.
    """
    return float(int(t / interval) % 2)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    p = argparse.ArgumentParser(
        description="Placebo strip video effect",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("input", help="Input video file")
    p.add_argument("output", help="Output video file")
    p.add_argument("--mode", choices=["lr", "ud", "both"], default="both",
                   help="lr = horizontal strips only, ud = vertical only, both = transition")
    p.add_argument("--n-lr", type=int, default=None, metavar="N",
                   help="Horizontal strips for the left-right phase (default 9 landscape, 16 portrait)")
    p.add_argument("--n-ud", type=int, default=None, metavar="N",
                   help="Vertical strips for the up-down phase (default 16 landscape, 9 portrait)")
    p.add_argument("--edge-margin", type=float, default=0.0, metavar="F",
                   help="How far short of the travel limit strips stop (0=reach limit, 0.2=20%% short)")
    p.add_argument("--overshoot", type=float, default=0.4, metavar="F",
                   help="How far past the canvas edge strips travel, as a fraction of frame size (0.4 = 40%%)")
    p.add_argument("--random-margin", type=float, default=0.05, metavar="F",
                   help="Max extra random margin re-rolled each full oscillation cycle per strip")
    p.add_argument("--freq", type=float, default=0.042,
                   help="Base oscillation frequency in Hz")
    p.add_argument("--freq-spread", type=float, default=0.35, metavar="F",
                   help="Per-strip frequency variation (0.35 = ±35%% of base freq)")
    p.add_argument("--phase-gap", type=float, default=math.pi,
                   help="Phase offset between adjacent strips (radians); pi = max anti-phase")
    p.add_argument("--max-speed", type=float, default=15, metavar="PX/S",
                   help="Max strip velocity in pixels/second (0 = auto: peak natural velocity for current amplitude+freq)")
    p.add_argument("--seed", type=int, default=42,
                   help="RNG seed for per-strip randomisation")
    p.add_argument("--canvas-expand", type=float, default=0.35,
                   help="Fractional canvas expansion (0.35 = 35%% larger each dimension)")
    p.add_argument("--bg", default=None,
                   help="Background color, 'cycle' to rotate through --colors, or unset (defaults to black, or cycle if --colors is given)")
    p.add_argument("--colors", nargs="+", default=None, metavar="COLOR",
                   help="Colors to cycle through (implies --bg cycle). Named (red, saddlebrown, …) or #RRGGBB hex.")
    p.add_argument("--color-hold", type=float, default=8.0, metavar="SEC",
                   help="Seconds each color is held at full brightness (cycle mode)")
    p.add_argument("--color-fade", action="store_true",
                   help="Fade each color in/out through black (cycle mode; off by default)")
    p.add_argument("--color-fade-secs", type=float, default=4.0, metavar="SEC",
                   help="Seconds to fade in/out through black when --color-fade is set")
    p.add_argument("--interval", type=float, default=14.0, metavar="SEC",
                   help="Seconds between L/R ↔ U/D alternations in both mode (0 = single transition)")
    p.add_argument("--transition-secs", type=float, default=-1.0, metavar="SEC",
                   help="Convergence window in seconds at each lr↔ud boundary (-1 = auto: 2×amplitude/max_speed)")
    p.add_argument("--fade-frames", type=int, default=24, metavar="N",
                   help="Fade to black over N frames at each mode-switch boundary (0 = disabled, try 100)")
    p.add_argument("--shadow-x", type=int, default=4, metavar="PX",
                   help="Drop shadow offset rightward in pixels (0 = disabled)")
    p.add_argument("--shadow-y", type=int, default=4, metavar="PX",
                   help="Drop shadow offset downward in pixels (0 = disabled)")
    p.add_argument("--shadow-color", default="black", metavar="COLOR",
                   help="Drop shadow color — named (red, white, …) or #RRGGBB hex")
    p.add_argument("--strip-sep", type=float, default=4.0, metavar="PX",
                   help="Peak gap between strips in pixels; rises then decays over the video")
    p.add_argument("--static-begin", type=float, default=0.0, metavar="SEC",
                   help="Seconds of unaltered video at the start before strips engage")
    p.add_argument("--static-end", type=float, default=0.0, metavar="SEC",
                   help="Seconds of unaltered video at the end after strips disengage")
    p.add_argument("--ramp-begin", type=float, default=3.0, metavar="SEC",
                   help="Seconds to ease-in strip amplitude after static-begin (cosine ramp, 0 = instant)")
    p.add_argument("--ramp-end", type=float, default=3.0, metavar="SEC",
                   help="Seconds to ease-out strip amplitude before static-end (cosine ramp, 0 = instant)")
    p.add_argument("--transition-at", type=float, default=0.5, metavar="F",
                   help="Fraction of video for single transition (both mode, interval=0 only)")
    p.add_argument("--transition-width", type=float, default=0.04, metavar="F",
                   help="Crossfade width as fraction of total duration (interval=0 only)")
    args = p.parse_args()

    # --colors implies --bg cycle unless --bg was explicitly set
    if args.colors is not None and args.bg is None:
        args.bg = "cycle"
    if args.colors is None:
        args.colors = DEFAULT_CYCLE_COLORS
    if args.bg is None:
        args.bg = "black"

    bg_spec = parse_color(args.bg)
    cycle_colors = [parse_color(c) for c in args.colors]

    cap = cv2.VideoCapture(args.input)
    if not cap.isOpened():
        sys.exit(f"Cannot open: {args.input}")

    fps   = cap.get(cv2.CAP_PROP_FPS)
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    W     = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    H     = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    # Auto strip counts: swap lr/ud defaults for portrait (tall) video.
    portrait = H > W
    if args.n_lr is None:
        args.n_lr = 16 if portrait else 9
    if args.n_ud is None:
        args.n_ud = 9 if portrait else 16
    if portrait:
        print(f"Portrait video detected ({W}×{H}) — using n_lr={args.n_lr}, n_ud={args.n_ud}")

    shadow_color = parse_color(args.shadow_color)

    pad_x  = int(W * args.canvas_expand / 2)
    pad_y  = int(H * args.canvas_expand / 2)
    W_out  = W + 2 * pad_x
    H_out  = H + 2 * pad_y

    # Hard travel limits: canvas edge + allowed overshoot past the canvas edge.
    clamp_lr = pad_x + int(W * args.overshoot)
    clamp_ud = pad_y + int(H * args.overshoot)

    # Base amplitudes: travel limit minus the edge margin buffer
    base_amp_lr = clamp_lr * (1.0 - args.edge_margin)
    base_amp_ud = clamp_ud * (1.0 - args.edge_margin)

    # Auto max-speed: peak natural velocity of the fastest possible strip
    # (amplitude × 2π × freq_max) so strips can actually reach their targets.
    # Sawtooth resets (~2×amp per frame) are still clamped to this value.
    if args.max_speed <= 0:
        max_freq = args.freq * (1.0 + args.freq_spread)
        max_speed = max(base_amp_lr, base_amp_ud) * 2 * math.pi * max_freq
    else:
        max_speed = args.max_speed
    max_delta = max_speed / fps

    # Auto transition-secs: with cosine ease the peak rate of change of desired
    # position is amp * π / transition_secs; physics can only track it when that
    # ≤ max_speed, so the minimum window is π * amp / max_speed.
    # Capped at 65% of interval so there's always meaningful full-effect time.
    transition_auto = args.transition_secs < 0
    if transition_auto:
        args.transition_secs = math.pi * max(base_amp_lr, base_amp_ud) / max_speed
        if args.interval > 0:
            args.transition_secs = min(args.transition_secs, args.interval * 0.65)

    print(f"Input:  {W}x{H} @ {fps:.2f} fps, {total} frames")
    print(f"Output: {W_out}x{H_out}  mode={args.mode}  "
          f"amp_lr={base_amp_lr:.1f}px  amp_ud={base_amp_ud:.1f}px  "
          f"max-speed={max_speed:.1f}px/s{'  (auto)' if args.max_speed <= 0 else ''}  "
          f"transition={args.transition_secs:.1f}s{'  (auto)' if transition_auto else ''}")

    params_lr = build_strip_params(args.n_lr, args.freq_spread, args.seed)
    params_ud = build_strip_params(args.n_ud, args.freq_spread, args.seed + 1)

    # Per-strip state
    margin_rng = np.random.default_rng(args.seed + 100)
    extra_margin_lr  = list(margin_rng.uniform(0.0, args.random_margin, args.n_lr))
    extra_margin_ud  = list(margin_rng.uniform(0.0, args.random_margin, args.n_ud))
    wave_prev_lr     = [0.0] * args.n_lr
    wave_prev_ud     = [0.0] * args.n_ud
    half_cycles_lr   = [0]   * args.n_lr
    half_cycles_ud   = [0]   * args.n_ud

    # Positions start at zero. The ramp factor is baked into desired positions
    # before physics, so strips naturally grow from zero rather than chasing
    # large pre-computed targets on the first rendered frame.
    pos_lr = [0.0] * args.n_lr
    pos_ud = [0.0] * args.n_ud

    fd_v, tmp_v = tempfile.mkstemp(suffix=".mp4")
    fd_a, tmp_a = tempfile.mkstemp(suffix=".aac")
    os.close(fd_v)
    os.close(fd_a)

    audio_ok = subprocess.run(
        ["ffmpeg", "-y", "-i", args.input, "-vn", "-acodec", "copy", tmp_a],
        capture_output=True,
    ).returncode == 0

    writer = cv2.VideoWriter(
        tmp_v, cv2.VideoWriter_fourcc(*"mp4v"), fps, (W_out, H_out),
    )

    half_w = args.transition_width / 2
    tr_lo  = args.transition_at - half_w
    tr_hi  = args.transition_at + half_w

    total_secs    = total / fps
    t_strip_start = args.static_begin
    t_strip_end   = total_secs - args.static_end
    active_dur    = max(t_strip_end - t_strip_start, 1.0 / fps)

    prev_phase = 0
    frame_idx = 0
    while True:
        ret, frame = cap.read()
        if not ret:
            break

        t        = frame_idx / fps
        progress = frame_idx / max(total - 1, 1)

        if bg_spec == "cycle":
            fade_secs = args.color_fade_secs if args.color_fade else 0.0
            bg = smooth_cycle_color(t, args.color_hold, fade_secs, cycle_colors)
        else:
            bg = bg_spec

        # Ramp: 0 during static periods, cosine ease during ramps, 1 at full effect.
        # Baked into desired so physics grows/shrinks naturally rather than bursting.
        ramp  = (ramp_in_factor(t, t_strip_start, args.ramp_begin)
                 * ramp_out_factor(t, t_strip_end, args.ramp_end))

        # Alignment factor: cosine ease to 0 at each lr↔ud boundary, back to 1.
        # Applied at draw time (not in desired) so pos_draw is guaranteed to be
        # exactly zero at the boundary frame regardless of physics position.
        a_fac = (align_factor(t, args.interval, args.transition_secs)
                 if args.mode == "both" and args.interval > 0 else 1.0)

        # At each mode boundary, reset the incoming mode's physics to zero.
        # Without this, the new mode has large physics positions and
        # pos_draw = large_pos * rising_a_fac accelerates visibly.
        curr_phase = int(t / args.interval) % 2 if args.mode == "both" and args.interval > 0 else 0
        if curr_phase != prev_phase:
            if curr_phase == 1:
                pos_ud = [0.0] * args.n_ud
            else:
                pos_lr = [0.0] * args.n_lr
        prev_phase = curr_phase

        # Always advance strip physics so motion is continuous when strips appear
        waves_lr = compute_waves(args.n_lr, t, args.freq, args.phase_gap, params_lr)
        waves_ud = compute_waves(args.n_ud, t, args.freq, args.phase_gap, params_ud)
        update_margins(waves_lr, wave_prev_lr, half_cycles_lr, extra_margin_lr, args.random_margin, margin_rng)
        update_margins(waves_ud, wave_prev_ud, half_cycles_ud, extra_margin_ud, args.random_margin, margin_rng)
        desired_lr = [waves_lr[i] * base_amp_lr * (1.0 - extra_margin_lr[i]) * ramp for i in range(args.n_lr)]
        desired_ud = [waves_ud[i] * base_amp_ud * (1.0 - extra_margin_ud[i]) * ramp for i in range(args.n_ud)]
        pos_lr = speed_limit(desired_lr, pos_lr, max_delta, clamp_lr)
        pos_ud = speed_limit(desired_ud, pos_ud, max_delta, clamp_ud)

        # Static begin / end: unaltered frame centred on canvas, no strip effects
        if t < t_strip_start or t >= t_strip_end:
            canvas = np.full((H_out, W_out, 3), bg, dtype=np.uint8)
            canvas[pad_y:pad_y + H, pad_x:pad_x + W] = frame
            result = canvas
        else:
            # Phase blend
            if args.mode == "lr":
                alpha = 0.0
            elif args.mode == "ud":
                alpha = 1.0
            elif args.interval > 0:
                alpha = alpha_for_interval(t, args.interval)
            elif progress <= tr_lo:
                alpha = 0.0
            elif progress >= tr_hi:
                alpha = 1.0
            else:
                alpha = (progress - tr_lo) / (tr_hi - tr_lo)

            if args.mode == "both" and args.fade_frames > 0:
                fac = fade_factor(t, args.interval, args.transition_at, total_secs,
                                  args.fade_frames, fps)
                if fac < 1.0:
                    frame = (frame.astype(np.float32) * fac).astype(np.uint8)

            # Separation uses progress within the active (non-static) window
            active_progress = (t - t_strip_start) / active_dur
            sep_val = strip_sep_value(active_progress, args.strip_sep)

            # a_fac=0 at the boundary guarantees visual alignment regardless of physics.
            # New-mode physics was reset to 0 at the cut so pos_new * rising_a_fac
            # grows from 0×0, preventing the acceleration burst.
            pos_lr_draw = [p * a_fac for p in pos_lr]
            pos_ud_draw = [p * a_fac for p in pos_ud]
            sep_draw    = sep_val * a_fac

            if alpha == 0.0:
                result = apply_lr(frame, args.n_lr, pos_lr_draw, bg, pad_x, pad_y,
                                   args.shadow_x, args.shadow_y, sep_draw, shadow_color)
            elif alpha == 1.0:
                result = apply_ud(frame, args.n_ud, pos_ud_draw, bg, pad_x, pad_y,
                                   args.shadow_x, args.shadow_y, sep_draw, shadow_color)
            else:
                lr = apply_lr(frame, args.n_lr, pos_lr_draw, bg, pad_x, pad_y,
                              args.shadow_x, args.shadow_y, sep_draw, shadow_color)
                ud = apply_ud(frame, args.n_ud, pos_ud_draw, bg, pad_x, pad_y,
                              args.shadow_x, args.shadow_y, sep_draw, shadow_color)
                result = blend_frames(lr, ud, alpha)

        writer.write(result)
        frame_idx += 1

        if frame_idx % 30 == 0:
            pct = 100 * frame_idx / max(total, 1)
            print(f"  {frame_idx}/{total} ({pct:.0f}%)", end="\r", flush=True)

    cap.release()
    writer.release()
    print(f"\nProcessed {frame_idx} frames")

    if audio_ok:
        r = subprocess.run(
            ["ffmpeg", "-y", "-i", tmp_v, "-i", tmp_a,
             "-c:v", "copy", "-c:a", "aac", "-shortest", args.output],
            capture_output=True,
        )
        if r.returncode != 0:
            print("Warning: audio mux failed, saving video-only")
            os.rename(tmp_v, args.output)
    else:
        print("No audio track found, saving video-only")
        subprocess.run(["ffmpeg", "-y", "-i", tmp_v, "-c:v", "copy", args.output],
                       capture_output=True)

    for f in (tmp_v, tmp_a):
        try:
            os.unlink(f)
        except FileNotFoundError:
            pass

    print(f"Done → {args.output}")


if __name__ == "__main__":
    main()
