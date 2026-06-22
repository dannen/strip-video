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

DEFAULT_CYCLE_COLORS = ["red", "green", "blue", "white", "black"]


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
    """Returns list of (freq_scale, waveform_name, extra_phase) per strip."""
    rng = np.random.default_rng(seed)
    params = []
    for _ in range(n_strips):
        freq_scale = float(rng.uniform(1.0 - freq_spread, 1.0 + freq_spread))
        waveform = WAVEFORM_NAMES[int(rng.integers(0, len(WAVEFORM_NAMES)))]
        extra_phase = float(rng.uniform(0, 2 * math.pi))
        params.append((freq_scale, waveform, extra_phase))
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

def apply_lr(frame, n_strips, offsets, bg, pad_x, pad_y):
    """Horizontal strips shifted left/right on expanded canvas."""
    h, w = frame.shape[:2]
    H_out, W_out = h + 2 * pad_y, w + 2 * pad_x
    canvas = np.full((H_out, W_out, 3), bg, dtype=np.uint8)
    strip_h = h // n_strips

    for i in range(n_strips):
        y0 = i * strip_h
        y1 = y0 + strip_h if i < n_strips - 1 else h
        strip = frame[y0:y1]
        off = int(offsets[i])

        dst_x = pad_x + off
        src_x0 = max(0, -dst_x)
        dst_x0 = max(0, dst_x)
        src_x1 = min(w, W_out - dst_x)
        if src_x1 > src_x0 and dst_x0 < W_out:
            canvas[pad_y + y0: pad_y + y1, dst_x0: dst_x0 + (src_x1 - src_x0)] = strip[:, src_x0:src_x1]

    return canvas


def apply_ud(frame, n_strips, offsets, bg, pad_x, pad_y):
    """Vertical strips shifted up/down on expanded canvas."""
    h, w = frame.shape[:2]
    H_out, W_out = h + 2 * pad_y, w + 2 * pad_x
    canvas = np.full((H_out, W_out, 3), bg, dtype=np.uint8)
    strip_w = w // n_strips

    for i in range(n_strips):
        x0 = i * strip_w
        x1 = x0 + strip_w if i < n_strips - 1 else w
        strip = frame[:, x0:x1]
        off = int(offsets[i])

        dst_y = pad_y + off
        src_y0 = max(0, -dst_y)
        dst_y0 = max(0, dst_y)
        src_y1 = min(h, H_out - dst_y)
        if src_y1 > src_y0 and dst_y0 < H_out:
            canvas[dst_y0: dst_y0 + (src_y1 - src_y0), pad_x + x0: pad_x + x1] = strip[src_y0:src_y1, :]

    return canvas


def blend_frames(a, b, alpha):
    return cv2.addWeighted(a, 1.0 - alpha, b, alpha, 0)


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


def alpha_for_interval(t, interval, fade_secs):
    """
    Returns blend alpha (0=lr, 1=ud) for repeating interval mode.
    Alternates lr→ud→lr every `interval` seconds with a crossfade at each boundary.
    """
    half_fade = fade_secs / 2
    boundary_n = round(t / interval)          # index of nearest boundary
    dist = t - boundary_n * interval          # signed distance from that boundary

    if boundary_n == 0 or abs(dist) >= half_fade:
        # Fully in one mode; which mode depends on which side of the nearest boundary
        return float(int(t / interval) % 2)

    # Inside crossfade window
    progress = (dist + half_fade) / fade_secs    # 0→1 across the window
    if boundary_n % 2 == 1:                       # odd boundary: lr→ud
        return max(0.0, min(1.0, progress))
    else:                                          # even boundary: ud→lr
        return max(0.0, min(1.0, 1.0 - progress))


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
    p.add_argument("--n-lr", type=int, default=16, metavar="N",
                   help="Horizontal strips for the left-right phase")
    p.add_argument("--n-ud", type=int, default=9, metavar="N",
                   help="Vertical strips for the up-down phase")
    p.add_argument("--edge-margin", type=float, default=0.1, metavar="F",
                   help="How far short of the canvas edge strips stop (0=touch edge, 0.2=20%% short)")
    p.add_argument("--random-margin", type=float, default=0.05, metavar="F",
                   help="Max extra random margin re-rolled each full oscillation cycle per strip")
    p.add_argument("--freq", type=float, default=0.3,
                   help="Base oscillation frequency in Hz")
    p.add_argument("--freq-spread", type=float, default=0.35, metavar="F",
                   help="Per-strip frequency variation (0.35 = ±35%% of base freq)")
    p.add_argument("--phase-gap", type=float, default=math.pi,
                   help="Phase offset between adjacent strips (radians); pi = max anti-phase")
    p.add_argument("--max-speed", type=float, default=25.0, metavar="PX/S",
                   help="Max strip velocity in pixels/second (0 = auto: peak natural velocity for current amplitude+freq)")
    p.add_argument("--seed", type=int, default=42,
                   help="RNG seed for per-strip randomisation")
    p.add_argument("--canvas-expand", type=float, default=0.2,
                   help="Fractional canvas expansion (0.2 = 20%% larger each dimension)")
    p.add_argument("--bg", default="black",
                   help="Background color or 'cycle' to rotate through --colors")
    p.add_argument("--colors", nargs="+", default=DEFAULT_CYCLE_COLORS, metavar="COLOR",
                   help="Colors to cycle through with --bg cycle. Named (red, saddlebrown, …) or #RRGGBB hex.")
    p.add_argument("--color-hold", type=float, default=8.0, metavar="SEC",
                   help="Seconds each color is held at full brightness (cycle mode)")
    p.add_argument("--color-fade", type=float, default=4.0, metavar="SEC",
                   help="Seconds to fade in/out through black (cycle mode)")
    p.add_argument("--interval", type=float, default=6.0, metavar="SEC",
                   help="Seconds between L/R ↔ U/D alternations in both mode (0 = single transition)")
    p.add_argument("--transition-secs", type=float, default=0.5, metavar="SEC",
                   help="Crossfade duration in seconds between modes (interval mode)")
    p.add_argument("--fade-frames", type=int, default=24, metavar="N",
                   help="Fade to black over N frames at each mode-switch boundary (0 = disabled, try 100)")
    p.add_argument("--transition-at", type=float, default=0.5, metavar="F",
                   help="Fraction of video for single transition (both mode, interval=0 only)")
    p.add_argument("--transition-width", type=float, default=0.04, metavar="F",
                   help="Crossfade width as fraction of total duration (interval=0 only)")
    args = p.parse_args()

    bg_spec = parse_color(args.bg)
    cycle_colors = [parse_color(c) for c in args.colors]

    cap = cv2.VideoCapture(args.input)
    if not cap.isOpened():
        sys.exit(f"Cannot open: {args.input}")

    fps   = cap.get(cv2.CAP_PROP_FPS)
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    W     = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    H     = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    pad_x  = int(W * args.canvas_expand / 2)
    pad_y  = int(H * args.canvas_expand / 2)
    W_out  = W + 2 * pad_x
    H_out  = H + 2 * pad_y

    # Base amplitudes: full pad minus the fixed edge margin
    base_amp_lr = pad_x * (1.0 - args.edge_margin)
    base_amp_ud = pad_y * (1.0 - args.edge_margin)

    # Auto max-speed: peak natural velocity of the fastest possible strip
    # (amplitude × 2π × freq_max) so strips can actually reach their targets.
    # Sawtooth resets (~2×amp per frame) are still clamped to this value.
    if args.max_speed <= 0:
        max_freq = args.freq * (1.0 + args.freq_spread)
        max_speed = max(base_amp_lr, base_amp_ud) * 2 * math.pi * max_freq
    else:
        max_speed = args.max_speed
    max_delta = max_speed / fps

    print(f"Input:  {W}x{H} @ {fps:.2f} fps, {total} frames")
    print(f"Output: {W_out}x{H_out}  mode={args.mode}  "
          f"amp_lr={base_amp_lr:.1f}px  amp_ud={base_amp_ud:.1f}px  "
          f"max-speed={max_speed:.1f}px/s{'  (auto)' if args.max_speed <= 0 else ''}")

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
    pos_lr           = [0.0] * args.n_lr
    pos_ud           = [0.0] * args.n_ud

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

    frame_idx = 0
    while True:
        ret, frame = cap.read()
        if not ret:
            break

        t        = frame_idx / fps
        progress = frame_idx / max(total - 1, 1)

        bg = smooth_cycle_color(t, args.color_hold, args.color_fade, cycle_colors) if bg_spec == "cycle" else bg_spec

        # Raw waveform values this frame
        waves_lr = compute_waves(args.n_lr, t, args.freq, args.phase_gap, params_lr)
        waves_ud = compute_waves(args.n_ud, t, args.freq, args.phase_gap, params_ud)

        # Re-roll random margins on full oscillation cycles
        update_margins(waves_lr, wave_prev_lr, half_cycles_lr, extra_margin_lr, args.random_margin, margin_rng)
        update_margins(waves_ud, wave_prev_ud, half_cycles_ud, extra_margin_ud, args.random_margin, margin_rng)

        # Desired offsets: wave × effective amplitude per strip
        desired_lr = [waves_lr[i] * base_amp_lr * (1.0 - extra_margin_lr[i]) for i in range(args.n_lr)]
        desired_ud = [waves_ud[i] * base_amp_ud * (1.0 - extra_margin_ud[i]) for i in range(args.n_ud)]

        # Speed limit + hard edge clamp
        pos_lr = speed_limit(desired_lr, pos_lr, max_delta, pad_x)
        pos_ud = speed_limit(desired_ud, pos_ud, max_delta, pad_y)

        # Phase blend
        if args.mode == "lr":
            alpha = 0.0
        elif args.mode == "ud":
            alpha = 1.0
        elif args.interval > 0:
            alpha = alpha_for_interval(t, args.interval, args.transition_secs)
        elif progress <= tr_lo:
            alpha = 0.0
        elif progress >= tr_hi:
            alpha = 1.0
        else:
            alpha = (progress - tr_lo) / (tr_hi - tr_lo)

        if args.mode == "both" and args.fade_frames > 0:
            total_secs = total / fps
            fac = fade_factor(t, args.interval, args.transition_at, total_secs,
                              args.fade_frames, fps)
            if fac < 1.0:
                frame = (frame.astype(np.float32) * fac).astype(np.uint8)

        if alpha == 0.0:
            result = apply_lr(frame, args.n_lr, pos_lr, bg, pad_x, pad_y)
        elif alpha == 1.0:
            result = apply_ud(frame, args.n_ud, pos_ud, bg, pad_x, pad_y)
        else:
            lr = apply_lr(frame, args.n_lr, pos_lr, bg, pad_x, pad_y)
            ud = apply_ud(frame, args.n_ud, pos_ud, bg, pad_x, pad_y)
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
