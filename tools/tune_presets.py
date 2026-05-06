"""
Re-generate ProjectPulsewire EasyEffects presets with research-backed tuning.

Tuning references:
  - Harman 2018 over-ear / in-ear target curve (Olive & Welti, AES preference work).
  - ISO 226:2003 / 2023 equal-loudness contours (loudness compensation presets).
  - B&K diffuse-field (neutral reference variants).
  - Public brand-voicing characteristics inferred from review / measurement
    databases (these are brand-INSPIRED, not factory profiles).

Run:
    python tools/tune_presets.py
    python tools/tune_presets.py --out path/to/output

The generator preserves each preset's existing plugin chain so the resulting
files remain drop-in compatible with EasyEffects and projectpulsewire's loader.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

# ──────────────────────────────────────────────────────────────────────
# 17-band ISO-octave EQ scaffolding (matches the existing presets).
# ──────────────────────────────────────────────────────────────────────

BANDS = (28, 45, 63, 90, 125, 180, 250, 355, 500, 710,
         1000, 1600, 2500, 4000, 6300, 10000, 14000)

# Q profile: broader at the lowest octaves so adjacent bells fuse into a
# smooth bass shelf, tightens through the Harman ear-gain region (1.6–4 kHz)
# for surgical presence, then broadens again at the very top for "air".
Q_PROFILE = (0.70, 0.78, 0.82, 0.86, 0.92, 0.95, 1.00, 1.00, 1.00, 1.00,
             1.00, 0.96, 0.92, 0.88, 0.84, 0.80, 0.75)


# ──────────────────────────────────────────────────────────────────────
# Plugin-block builders (match exact key set used by EasyEffects / LSP).
# ──────────────────────────────────────────────────────────────────────

def build_band(freq: float, gain: float, q: float) -> dict:
    return {
        "frequency": freq,
        "gain": round(float(gain), 2),
        "mode": "APO (DR)",
        "mute": False,
        "q": round(float(q), 2),
        "slope": "x1",
        "solo": False,
        "type": "Bell",
        "width": 4.0,
    }


def build_eq_channel(gains: tuple) -> dict:
    return {f"band{i}": build_band(BANDS[i], gains[i], Q_PROFILE[i])
            for i in range(len(BANDS))}


def auto_input_gain(gains: tuple, has_bass_enh: bool) -> float:
    """Pre-EQ headroom guard: scale ~55% of the loudest positive band, with
    extra margin if a bass_enhancer follows (it adds harmonic energy)."""
    max_pos = max((g for g in gains if g > 0), default=0.0)
    pad = 0.5 if has_bass_enh else 0.0
    return round(-max_pos * 0.55 - pad, 1)


def build_eq(gains: tuple, has_bass_enh: bool) -> dict:
    chan = build_eq_channel(gains)
    return {
        "balance": 0.0,
        "bypass": False,
        "input-gain": auto_input_gain(gains, has_bass_enh),
        "left": chan,
        "mode": "IIR",
        "num-bands": 17,
        "output-gain": -0.2,
        "pitch-left": 0.0,
        "pitch-right": 0.0,
        "right": chan,
        "split-channels": False,
    }


def build_compressor(attack=22.0, threshold=-19.0, ratio=1.8, release=180.0,
                     makeup=0.6, knee=-10.0) -> dict:
    return {
        "attack": float(attack),
        "boost-amount": 4.5,
        "boost-threshold": -72.0,
        "bypass": False,
        "dry": -100.0,
        "hpf-frequency": 10.0,
        "hpf-mode": "Off",
        "input-gain": 0.0,
        "knee": float(knee),
        "lpf-frequency": 20000.0,
        "lpf-mode": "Off",
        "makeup": float(makeup),
        "mode": "Downward",
        "output-gain": 0.0,
        "ratio": float(ratio),
        "release": float(release),
        "release-threshold": -100.0,
        "sidechain": {
            "lookahead": 10.0,
            "mode": "RMS",
            "preamp": 0.0,
            "reactivity": 10.0,
            "source": "Middle",
            "stereo-split-source": "Left/Right",
            "type": "Feed-forward",
        },
        "stereo-split": False,
        "threshold": float(threshold),
        "wet": 0.0,
    }


def build_bass_enhancer(amount=1.8, harmonics=4.6, scope=78.0,
                        blend=-3.0, floor=32.0) -> dict:
    return {
        "amount": float(amount),
        "blend": float(blend),
        "bypass": False,
        "floor": float(floor),
        "floor-active": True,
        "harmonics": float(harmonics),
        "input-gain": 0.0,
        "output-gain": 0.0,
        "scope": float(scope),
    }


def build_bass_loudness(loudness=-0.5, output=-3.5, link=-5.5) -> dict:
    return {
        "bypass": False,
        "input-gain": 0.0,
        "link": float(link),
        "loudness": float(loudness),
        "output": float(output),
        "output-gain": 0.0,
    }


def build_maximizer(threshold=-6.0, release=40.0) -> dict:
    return {
        "bypass": False,
        "input-gain": 0.0,
        "output-gain": 0.0,
        "release": float(release),
        "threshold": float(threshold),
    }


def build_limiter(threshold=-1.2, attack=5.0, release=14.0,
                  lookahead=5.0, mode="Herm Thin",
                  oversampling="None") -> dict:
    return {
        "alr": False,
        "alr-attack": 5.0,
        "alr-knee": 0.0,
        "alr-knee-smooth": -5.0,
        "alr-release": 50.0,
        "attack": float(attack),
        "bypass": False,
        "dithering": "None",
        "gain-boost": False,
        "input-gain": 0.0,
        "lookahead": float(lookahead),
        "mode": mode,
        "output-gain": 0.0,
        "oversampling": oversampling,
        "release": float(release),
        "sidechain-preamp": 0.0,
        "stereo-link": 100.0,
        "threshold": float(threshold),
    }


# ──────────────────────────────────────────────────────────────────────
# Chain assembly: A = comp→eq→lim, B = comp→eq→be→lim,
#                 C = bl→eq→be→max→lim
# ──────────────────────────────────────────────────────────────────────

def assemble(gains: tuple, chain: str, dyn: dict) -> dict:
    # Insertion order here is the order keys appear in the resulting JSON.
    # We keep blocklist + plugins_order at the top to match the existing
    # preset layout, then emit each plugin block in chain order.
    if chain == "A":
        order = ["compressor#0", "equalizer#0", "limiter#0"]
        blocks = {
            "compressor#0": build_compressor(**dyn.get("comp", {})),
            "equalizer#0":  build_eq(gains, has_bass_enh=False),
            "limiter#0":    build_limiter(**dyn.get("lim", {})),
        }
    elif chain == "B":
        order = ["compressor#0", "equalizer#0", "bass_enhancer#0", "limiter#0"]
        blocks = {
            "compressor#0":    build_compressor(**dyn.get("comp", {})),
            "equalizer#0":     build_eq(gains, has_bass_enh=True),
            "bass_enhancer#0": build_bass_enhancer(**dyn.get("be", {})),
            "limiter#0":       build_limiter(**dyn.get("lim", {})),
        }
    elif chain == "C":
        order = ["bass_loudness#0", "equalizer#0", "bass_enhancer#0",
                 "maximizer#0", "limiter#0"]
        blocks = {
            "bass_loudness#0": build_bass_loudness(**dyn.get("bl", {})),
            "equalizer#0":     build_eq(gains, has_bass_enh=True),
            "bass_enhancer#0": build_bass_enhancer(**dyn.get("be", {})),
            "maximizer#0":     build_maximizer(**dyn.get("max", {})),
            "limiter#0":       build_limiter(**dyn.get("lim", {})),
        }
    else:
        raise ValueError(f"Unknown chain type: {chain!r}")
    out = {"blocklist": [], "plugins_order": order}
    out.update(blocks)
    return {"output": out}


# ──────────────────────────────────────────────────────────────────────
# 47 voicing profiles.
#
# Each entry:  name, chain, 17-band gains (dB), dynamics overrides.
#
# Gain interpretation (one float per BAND in this order):
#   28  45  63  90  125 180 250 355 500 710 1k  1.6k 2.5k 4k  6.3k 10k 14k
#
# Notes on shape vocabulary:
#   * "Harman bass shelf"   = +4–6 dB ramp peaking 60–90 Hz, neutral by 250 Hz
#   * "ear-gain peak"       = +2–3 dB at 2.5–4 kHz (Harman target)
#   * "V-shape"             = bass shelf + scooped 250–710 Hz + treble shelf
#   * "smile"               = gentle bass + neutral mids + gentle air shelf
#   * "vocal-forward"       = bass cut, +1–4 kHz lift, controlled top
#   * "loudness curve"      = ISO-226 inspired: more bass + lifted highs at
#                             low SPL, bass_loudness plugin handles dynamic
#                             tilt, EQ adds the static portion.
# ──────────────────────────────────────────────────────────────────────

VOICINGS: list[dict] = [

    # ─── BASS family (10) ───────────────────────────────────────────────
    {
        "name": "Bass - Punchy Everyday",
        "chain": "B",
        "gains": (1.5, 3.5, 4.5, 4.0, 2.5, 1.0, 0.0, -0.5, -0.3, 0.0,
                  0.3, 1.0, 2.0, 1.8, 1.2, 0.5, 0.0),
        "dyn": {
            "comp": {"attack": 18, "threshold": -18.5, "ratio": 1.9,
                     "release": 150, "makeup": 0.7},
            "be":   {"amount": 2.0, "harmonics": 4.8, "scope": 78},
            "lim":  {"threshold": -1.2},
        },
    },
    {
        "name": "Bass - Deep Sub Lift",
        "chain": "B",
        "gains": (3.5, 4.8, 5.0, 3.5, 1.8, 0.5, 0.0, -0.3, 0.0, 0.0,
                  0.0, 0.3, 0.8, 0.6, 0.4, 0.2, 0.0),
        "dyn": {
            "comp": {"attack": 20, "threshold": -19.0, "ratio": 1.8,
                     "release": 175, "makeup": 0.7},
            "be":   {"amount": 2.4, "harmonics": 5.0, "scope": 82,
                     "floor": 28},
            "lim":  {"threshold": -1.0},
        },
    },
    {
        "name": "Bass - Warm Consumer",
        "chain": "B",
        "gains": (2.0, 4.0, 5.0, 4.5, 3.5, 2.0, 0.8, 0.2, -0.2, -0.3,
                  -0.2, 0.2, 0.8, 0.5, -0.2, -0.6, -0.8),
        "dyn": {
            "comp": {"attack": 22, "threshold": -19.5, "ratio": 1.8,
                     "release": 180, "makeup": 0.7},
            "be":   {"amount": 1.8, "harmonics": 4.6, "scope": 76},
            "lim":  {"threshold": -1.2},
        },
    },
    {
        "name": "Bass - Tight Kick",
        "chain": "B",
        "gains": (1.0, 2.5, 4.5, 5.5, 3.5, 0.5, -1.5, -1.0, 0.0, 0.5,
                  0.8, 1.5, 2.0, 1.5, 1.0, 0.5, 0.0),
        "dyn": {
            "comp": {"attack": 14, "threshold": -18.0, "ratio": 2.0,
                     "release": 130, "makeup": 0.8},
            "be":   {"amount": 1.6, "harmonics": 4.4, "scope": 72,
                     "floor": 36},
            "lim":  {"threshold": -1.2},
        },
    },
    {
        "name": "Bass - Club V-Shape",
        "chain": "B",
        "gains": (3.0, 4.5, 5.5, 4.5, 2.0, -0.5, -2.0, -2.5, -2.0, -1.0,
                  0.0, 1.0, 2.5, 3.5, 3.5, 2.5, 1.5),
        "dyn": {
            "comp": {"attack": 16, "threshold": -18.0, "ratio": 2.0,
                     "release": 140, "makeup": 0.8},
            "be":   {"amount": 2.4, "harmonics": 5.2, "scope": 84,
                     "floor": 30},
            "lim":  {"threshold": -1.0},
        },
    },
    {
        "name": "Bass - Clean Bass Lift",
        "chain": "B",
        "gains": (2.0, 3.5, 4.0, 3.5, 2.0, 0.5, 0.0, 0.0, 0.0, 0.0,
                  0.0, 0.3, 0.8, 0.6, 0.3, 0.0, 0.0),
        "dyn": {
            "comp": {"attack": 22, "threshold": -19.5, "ratio": 1.7,
                     "release": 190, "makeup": 0.5},
            "be":   {"amount": 1.4, "harmonics": 4.0, "scope": 70},
            "lim":  {"threshold": -1.3},
        },
    },
    {
        "name": "Bass - Bass + Clarity",
        "chain": "B",
        "gains": (2.5, 4.0, 4.5, 3.8, 1.5, -0.5, -1.0, -0.5, 0.0, 0.3,
                  0.8, 1.8, 2.8, 2.5, 1.8, 1.0, 0.5),
        "dyn": {
            "comp": {"attack": 18, "threshold": -18.5, "ratio": 1.9,
                     "release": 150, "makeup": 0.7},
            "be":   {"amount": 1.8, "harmonics": 4.8, "scope": 78},
            "lim":  {"threshold": -1.2},
        },
    },
    {
        "name": "Bass - Bass + Loudness",
        "chain": "C",
        "gains": (3.0, 4.5, 4.8, 3.5, 2.0, 0.5, 0.0, -0.3, 0.0, 0.3,
                  0.5, 1.2, 2.0, 1.8, 1.5, 1.0, 0.5),
        "dyn": {
            "bl":  {"loudness": 1.5, "output": -4.0, "link": -6.5},
            "be":  {"amount": 1.8, "harmonics": 4.6, "scope": 76},
            "max": {"threshold": -6.5, "release": 40},
            "lim": {"threshold": -1.1},
        },
    },
    {
        "name": "Bass - Late Night Bass",
        "chain": "C",
        "gains": (2.5, 3.8, 4.0, 3.0, 1.5, 0.3, -0.2, -0.5, -0.3, 0.0,
                  0.0, 0.5, 1.0, 0.5, -0.3, -0.8, -1.0),
        "dyn": {
            "bl":  {"loudness": -1.0, "output": -4.5, "link": -4.5},
            "be":  {"amount": 1.4, "harmonics": 4.0, "scope": 72},
            "max": {"threshold": -8.0, "release": 50},
            "lim": {"threshold": -1.5},
        },
    },
    {
        "name": "Bass - Speaker Rescue",
        "chain": "C",
        "gains": (4.5, 5.5, 5.5, 4.0, 2.0, 0.5, -0.3, -0.5, 0.0, 0.5,
                  1.0, 1.8, 2.5, 2.0, 1.2, 0.5, 0.0),
        "dyn": {
            "bl":  {"loudness": 3.0, "output": -4.5, "link": -7.5},
            "be":  {"amount": 2.6, "harmonics": 5.4, "scope": 84,
                    "floor": 26},
            "max": {"threshold": -5.5, "release": 35},
            "lim": {"threshold": -1.0},
        },
    },

    # ─── BRAND family (8) ───────────────────────────────────────────────
    # Voicings inferred from public reviews / measurements; not factory.
    {
        "name": "Brand - Bose Warm",
        "chain": "B",
        "gains": (1.5, 3.5, 4.3, 4.5, 3.0, 1.5, 0.5, 0.0, -0.5, -1.0,
                  -1.2, -0.5, 0.5, 0.0, -0.8, -1.3, -1.5),
        "dyn": {
            "comp": {"attack": 22, "threshold": -19.5, "ratio": 1.8,
                     "release": 175, "makeup": 0.7},
            "be":   {"amount": 1.6, "harmonics": 4.2, "scope": 74},
            "lim":  {"threshold": -1.3},
        },
    },
    {
        "name": "Brand - Bose Smooth Bass",
        "chain": "B",
        "gains": (2.5, 4.0, 4.8, 4.2, 2.5, 1.2, 0.3, -0.3, -0.8, -1.0,
                  -1.0, -0.3, 0.3, -0.2, -1.0, -1.5, -1.8),
        "dyn": {
            "comp": {"attack": 22, "threshold": -19.5, "ratio": 1.8,
                     "release": 180, "makeup": 0.7},
            "be":   {"amount": 1.8, "harmonics": 4.4, "scope": 76},
            "lim":  {"threshold": -1.3},
        },
    },
    {
        "name": "Brand - JBL Pure Bass",
        "chain": "B",
        "gains": (3.0, 4.5, 5.2, 4.0, 1.8, -0.5, -1.5, -1.0, -0.3, 0.0,
                  0.3, 1.5, 2.5, 3.0, 3.0, 2.0, 1.0),
        "dyn": {
            "comp": {"attack": 18, "threshold": -18.5, "ratio": 1.9,
                     "release": 150, "makeup": 0.8},
            "be":   {"amount": 2.2, "harmonics": 5.0, "scope": 80},
            "lim":  {"threshold": -1.1},
        },
    },
    {
        "name": "Brand - JBL Party V",
        "chain": "B",
        "gains": (3.5, 5.0, 5.8, 4.5, 2.0, -0.5, -2.0, -1.5, -0.5, 0.0,
                  0.3, 1.8, 3.0, 3.8, 3.5, 2.5, 1.5),
        "dyn": {
            "comp": {"attack": 16, "threshold": -18.0, "ratio": 2.0,
                     "release": 140, "makeup": 0.8},
            "be":   {"amount": 2.4, "harmonics": 5.2, "scope": 84,
                     "floor": 28},
            "lim":  {"threshold": -1.0},
        },
    },
    {
        "name": "Brand - Harman Reference",
        "chain": "A",
        # Olive/Welti 2018 over-ear target, scaled and discretised onto our 17 bands.
        "gains": (1.2, 2.8, 3.2, 2.9, 1.6, 0.4, -0.5, -1.0, -0.8, -0.3,
                  0.4, 1.5, 2.8, 2.5, 1.5, 0.4, -0.1),
        "dyn": {
            "comp": {"attack": 26, "threshold": -20.5, "ratio": 1.7,
                     "release": 190, "makeup": 0.5},
            "lim":  {"threshold": -1.3},
        },
    },
    {
        "name": "Brand - Harman Kardon Lounge",
        "chain": "A",
        "gains": (1.5, 3.0, 3.8, 3.5, 2.0, 0.8, 0.0, -0.5, -0.3, 0.0,
                  0.5, 1.2, 1.8, 1.2, 0.3, -0.5, -0.8),
        "dyn": {
            "comp": {"attack": 24, "threshold": -20.0, "ratio": 1.7,
                     "release": 200, "makeup": 0.5},
            "lim":  {"threshold": -1.3},
        },
    },
    {
        "name": "Brand - Sony Excited",
        "chain": "B",
        "gains": (2.8, 4.2, 5.0, 3.8, 1.5, -0.3, -1.0, -0.8, 0.0, 0.5,
                  0.8, 2.0, 2.8, 3.2, 3.5, 2.8, 2.0),
        "dyn": {
            "comp": {"attack": 18, "threshold": -18.5, "ratio": 1.9,
                     "release": 150, "makeup": 0.8},
            "be":   {"amount": 2.0, "harmonics": 4.8, "scope": 80},
            "lim":  {"threshold": -1.1},
        },
    },
    {
        "name": "Brand - Sony Bright",
        "chain": "A",
        "gains": (1.0, 2.0, 2.5, 2.0, 1.0, 0.3, 0.0, -0.3, -0.2, 0.0,
                  0.5, 1.5, 2.5, 2.8, 2.8, 2.2, 1.5),
        "dyn": {
            "comp": {"attack": 22, "threshold": -19.5, "ratio": 1.8,
                     "release": 170, "makeup": 0.6},
            "lim":  {"threshold": -1.2},
        },
    },

    # ─── GENRE family (14) ──────────────────────────────────────────────
    {
        "name": "Genre - EDM Festival",
        "chain": "B",
        "gains": (3.5, 4.8, 5.5, 4.5, 2.0, -0.5, -2.0, -1.8, -0.8, 0.0,
                  0.3, 1.5, 2.8, 3.5, 3.5, 2.8, 2.0),
        "dyn": {
            "comp": {"attack": 14, "threshold": -18.0, "ratio": 2.0,
                     "release": 130, "makeup": 0.8},
            "be":   {"amount": 2.4, "harmonics": 5.2, "scope": 84,
                     "floor": 28},
            "lim":  {"threshold": -1.0},
        },
    },
    {
        "name": "Genre - EDM Smooth",
        "chain": "B",
        "gains": (2.5, 3.8, 4.5, 3.5, 1.5, -0.3, -1.2, -1.0, -0.3, 0.3,
                  0.5, 1.5, 2.2, 2.5, 2.0, 1.2, 0.5),
        "dyn": {
            "comp": {"attack": 18, "threshold": -18.5, "ratio": 1.9,
                     "release": 150, "makeup": 0.7},
            "be":   {"amount": 1.8, "harmonics": 4.6, "scope": 78},
            "lim":  {"threshold": -1.2},
        },
    },
    {
        "name": "Genre - Rock Arena",
        "chain": "A",
        "gains": (1.0, 2.5, 3.5, 4.0, 3.0, 1.5, 0.0, -0.3, 0.5, 1.0,
                  1.5, 2.5, 3.0, 2.5, 1.8, 1.0, 0.3),
        "dyn": {
            "comp": {"attack": 18, "threshold": -19.0, "ratio": 1.9,
                     "release": 160, "makeup": 0.7},
            "lim":  {"threshold": -1.2},
        },
    },
    {
        "name": "Genre - Rock Classic",
        "chain": "A",
        "gains": (0.8, 2.0, 3.0, 3.5, 3.0, 2.0, 1.0, 0.5, 0.8, 1.2,
                  1.5, 2.0, 2.0, 1.2, 0.3, -0.5, -0.8),
        "dyn": {
            "comp": {"attack": 22, "threshold": -19.5, "ratio": 1.8,
                     "release": 175, "makeup": 0.6},
            "lim":  {"threshold": -1.3},
        },
    },
    {
        "name": "Genre - Classical Wide",
        "chain": "A",
        "gains": (0.8, 1.5, 1.8, 1.5, 0.8, 0.3, 0.0, -0.3, 0.0, 0.3,
                  0.5, 0.8, 1.2, 1.5, 1.5, 1.2, 0.8),
        "dyn": {
            "comp": {"attack": 28, "threshold": -21.0, "ratio": 1.6,
                     "release": 220, "makeup": 0.4},
            "lim":  {"threshold": -1.5},
        },
    },
    {
        "name": "Genre - Classical Warm",
        "chain": "A",
        "gains": (1.0, 1.8, 2.2, 2.0, 1.5, 1.0, 0.5, 0.3, 0.5, 0.8,
                  1.0, 1.0, 0.8, 0.3, -0.3, -0.8, -1.0),
        "dyn": {
            "comp": {"attack": 28, "threshold": -21.0, "ratio": 1.6,
                     "release": 220, "makeup": 0.4},
            "lim":  {"threshold": -1.5},
        },
    },
    {
        "name": "Genre - Lo-Fi Soft",
        "chain": "A",
        "gains": (1.5, 2.5, 3.0, 3.2, 2.8, 2.0, 1.5, 1.0, 0.5, 0.3,
                  0.0, -0.3, -0.5, -1.0, -1.5, -2.0, -2.5),
        "dyn": {
            "comp": {"attack": 24, "threshold": -20.0, "ratio": 1.7,
                     "release": 200, "makeup": 0.5},
            "lim":  {"threshold": -1.4},
        },
    },
    {
        "name": "Genre - Lo-Fi Air",
        "chain": "A",
        "gains": (1.2, 2.0, 2.5, 2.8, 2.5, 1.8, 1.2, 0.5, 0.0, -0.2,
                  -0.3, -0.5, -0.3, 0.5, 1.2, 1.8, 2.0),
        "dyn": {
            "comp": {"attack": 24, "threshold": -20.0, "ratio": 1.7,
                     "release": 200, "makeup": 0.5},
            "lim":  {"threshold": -1.3},
        },
    },
    {
        "name": "Genre - Indie Presence",
        "chain": "A",
        "gains": (0.5, 1.5, 2.0, 2.0, 1.5, 1.0, 0.5, 0.5, 1.5, 2.5,
                  2.8, 2.5, 2.0, 1.5, 1.0, 0.5, 0.0),
        "dyn": {
            "comp": {"attack": 22, "threshold": -19.5, "ratio": 1.8,
                     "release": 170, "makeup": 0.6},
            "lim":  {"threshold": -1.3},
        },
    },
    {
        "name": "Genre - Indie Warm",
        "chain": "A",
        "gains": (1.0, 2.0, 2.8, 3.0, 2.5, 1.8, 1.2, 0.8, 1.0, 1.5,
                  1.8, 1.5, 1.0, 0.3, -0.3, -0.8, -1.0),
        "dyn": {
            "comp": {"attack": 22, "threshold": -19.5, "ratio": 1.8,
                     "release": 175, "makeup": 0.6},
            "lim":  {"threshold": -1.3},
        },
    },
    {
        "name": "Genre - K-Pop Sparkle",
        "chain": "A",
        "gains": (1.5, 2.5, 3.0, 2.5, 1.5, 0.5, 0.0, 0.0, 0.5, 1.5,
                  2.0, 2.5, 3.0, 3.2, 3.0, 2.5, 1.8),
        "dyn": {
            "comp": {"attack": 16, "threshold": -18.0, "ratio": 1.9,
                     "release": 135, "makeup": 0.8},
            "lim":  {"threshold": -1.1},
        },
    },
    {
        "name": "Genre - K-Pop Impact",
        "chain": "B",
        "gains": (2.5, 3.8, 4.5, 3.5, 1.8, 0.0, -0.5, -0.3, 0.3, 1.0,
                  1.5, 2.2, 3.0, 3.2, 3.0, 2.2, 1.5),
        "dyn": {
            "comp": {"attack": 16, "threshold": -18.0, "ratio": 2.0,
                     "release": 140, "makeup": 0.8},
            "be":   {"amount": 2.0, "harmonics": 4.8, "scope": 80},
            "lim":  {"threshold": -1.1},
        },
    },
    {
        "name": "Genre - Hi-Fi Reference",
        "chain": "A",
        "gains": (0.8, 1.5, 1.8, 1.5, 0.8, 0.2, -0.3, -0.5, -0.3, 0.0,
                  0.3, 1.0, 1.8, 1.5, 0.8, 0.2, 0.0),
        "dyn": {
            "comp": {"attack": 28, "threshold": -21.0, "ratio": 1.6,
                     "release": 210, "makeup": 0.4},
            "lim":  {"threshold": -1.4},
        },
    },
    {
        "name": "Genre - Hi-Fi Rich",
        "chain": "A",
        "gains": (1.0, 2.0, 2.5, 2.2, 1.5, 0.8, 0.0, -0.3, 0.0, 0.5,
                  0.8, 1.5, 2.2, 2.0, 1.2, 0.5, 0.0),
        "dyn": {
            "comp": {"attack": 26, "threshold": -20.5, "ratio": 1.7,
                     "release": 200, "makeup": 0.5},
            "lim":  {"threshold": -1.3},
        },
    },

    # ─── VOICE family (8) ───────────────────────────────────────────────
    {
        "name": "Voice - Dialogue Focus",
        "chain": "A",
        "gains": (-2.0, -1.0, -0.3, 0.0, 0.5, 1.0, 2.0, 2.8, 3.5, 3.8,
                  3.5, 3.0, 2.5, 1.5, 0.5, 0.0, -0.3),
        "dyn": {
            "comp": {"attack": 16, "threshold": -19.0, "ratio": 2.2,
                     "release": 140, "makeup": 0.8},
            "lim":  {"threshold": -1.3},
        },
    },
    {
        "name": "Voice - Dialogue Night",
        "chain": "C",
        "gains": (-1.5, -0.5, 0.0, 0.5, 1.0, 1.5, 2.5, 3.0, 3.5, 3.8,
                  3.5, 3.0, 2.0, 1.0, 0.5, 0.3, 0.0),
        "dyn": {
            "bl":  {"loudness": -1.5, "output": -4.0, "link": -3.5},
            "be":  {"amount": 1.0, "harmonics": 3.6, "scope": 66},
            "max": {"threshold": -8.0, "release": 50},
            "lim": {"threshold": -1.5},
        },
    },
    {
        "name": "Voice - Podcast Clear",
        "chain": "A",
        "gains": (-1.5, -0.8, -0.3, 0.0, 0.5, 1.2, 2.0, 2.5, 2.8, 2.5,
                  2.0, 1.5, 1.2, 0.5, 0.0, -0.3, -0.5),
        "dyn": {
            "comp": {"attack": 18, "threshold": -19.5, "ratio": 2.1,
                     "release": 150, "makeup": 0.8},
            "lim":  {"threshold": -1.4},
        },
    },
    {
        "name": "Voice - Vocal Warmth",
        "chain": "A",
        "gains": (0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 2.0, 1.5, 1.5, 2.0,
                  2.2, 2.0, 1.8, 1.0, 0.3, -0.3, -0.5),
        "dyn": {
            "comp": {"attack": 22, "threshold": -19.5, "ratio": 1.9,
                     "release": 170, "makeup": 0.7},
            "lim":  {"threshold": -1.3},
        },
    },
    {
        "name": "Voice - Gaming Footsteps",
        "chain": "A",
        "gains": (-2.0, -1.5, -1.0, -0.5, -1.5, -2.0, -1.0, -0.3, 0.5, 1.5,
                  2.0, 2.5, 3.0, 4.0, 4.0, 2.5, 1.0),
        "dyn": {
            "comp": {"attack": 14, "threshold": -19.0, "ratio": 2.0,
                     "release": 130, "makeup": 0.8},
            "lim":  {"threshold": -1.3},
        },
    },
    {
        "name": "Voice - Gaming Immersion",
        "chain": "B",
        "gains": (3.0, 4.5, 5.2, 4.0, 1.8, -0.3, -1.5, -1.5, -0.5, 0.5,
                  1.0, 2.0, 2.8, 3.5, 3.5, 2.5, 1.5),
        "dyn": {
            "comp": {"attack": 16, "threshold": -18.5, "ratio": 2.0,
                     "release": 140, "makeup": 0.8},
            "be":   {"amount": 2.2, "harmonics": 5.0, "scope": 82},
            "lim":  {"threshold": -1.0},
        },
    },
    {
        "name": "Voice - Video Balanced",
        "chain": "A",
        "gains": (0.5, 1.0, 1.5, 1.8, 1.5, 1.0, 0.8, 1.2, 2.0, 2.5,
                  2.5, 2.0, 1.8, 1.2, 0.5, 0.0, -0.3),
        "dyn": {
            "comp": {"attack": 20, "threshold": -19.5, "ratio": 1.9,
                     "release": 165, "makeup": 0.7},
            "lim":  {"threshold": -1.3},
        },
    },
    {
        "name": "Voice - Live Stage",
        "chain": "A",
        "gains": (0.8, 1.8, 2.5, 2.8, 2.0, 1.0, 0.3, 0.5, 1.5, 2.5,
                  2.8, 2.5, 2.0, 1.5, 1.0, 0.5, 0.0),
        "dyn": {
            "comp": {"attack": 20, "threshold": -19.0, "ratio": 1.9,
                     "release": 160, "makeup": 0.7},
            "lim":  {"threshold": -1.2},
        },
    },

    # ─── DYNAMICS family (7) ────────────────────────────────────────────
    {
        "name": "Dynamics - Loudness Light",
        "chain": "C",
        "gains": (2.0, 3.5, 4.0, 3.5, 2.0, 0.8, 0.0, -0.3, 0.0, 0.3,
                  0.5, 1.2, 2.0, 1.8, 1.2, 0.5, -0.3),
        "dyn": {
            "bl":  {"loudness": -1.0, "output": -3.5, "link": -5.5},
            "be":  {"amount": 1.2, "harmonics": 3.8, "scope": 68},
            "max": {"threshold": -7.0, "release": 40},
            "lim": {"threshold": -1.3},
        },
    },
    {
        "name": "Dynamics - Loudness Deep",
        "chain": "C",
        "gains": (3.0, 4.5, 5.0, 4.0, 2.5, 1.0, 0.0, -0.3, 0.0, 0.3,
                  0.8, 1.8, 2.8, 2.5, 2.0, 1.2, 0.3),
        "dyn": {
            "bl":  {"loudness": 2.0, "output": -4.0, "link": -7.0},
            "be":  {"amount": 1.8, "harmonics": 4.6, "scope": 76},
            "max": {"threshold": -6.0, "release": 38},
            "lim": {"threshold": -1.1},
        },
    },
    {
        "name": "Dynamics - Auto Gain Soft",
        "chain": "A",
        "gains": (1.0, 2.0, 2.5, 2.2, 1.2, 0.5, 0.0, -0.3, 0.0, 0.3,
                  0.5, 1.0, 1.5, 1.0, 0.5, 0.0, -0.3),
        "dyn": {
            "comp": {"attack": 22, "threshold": -20.0, "ratio": 1.8,
                     "release": 180, "makeup": 0.6},
            "lim":  {"threshold": -1.3},
        },
    },
    {
        "name": "Dynamics - Auto Gain Punch",
        "chain": "A",
        "gains": (1.2, 2.5, 3.0, 2.8, 1.5, 0.3, -0.5, -0.3, 0.5, 1.5,
                  2.0, 2.2, 2.5, 2.0, 1.0, 0.3, -0.3),
        "dyn": {
            "comp": {"attack": 12, "threshold": -19.0, "ratio": 2.4,
                     "release": 130, "makeup": 1.0},
            "lim":  {"threshold": -1.1},
        },
    },
    {
        "name": "Dynamics - Crystal Detail",
        "chain": "A",
        "gains": (0.5, 1.5, 2.0, 1.8, 1.0, 0.3, 0.0, 0.0, 0.3, 0.8,
                  1.0, 1.5, 2.0, 2.2, 2.0, 1.5, 1.0),
        "dyn": {
            "comp": {"attack": 26, "threshold": -20.5, "ratio": 1.6,
                     "release": 200, "makeup": 0.4},
            "lim":  {"threshold": -1.4},
        },
    },
    {
        "name": "Dynamics - Late Night",
        "chain": "C",
        "gains": (-1.5, -1.0, -0.5, 0.0, 0.5, 1.0, 1.5, 1.8, 2.0, 1.8,
                  1.5, 1.2, 1.0, 0.5, 0.0, -0.3, -0.5),
        "dyn": {
            "bl":  {"loudness": -2.5, "output": -5.0, "link": -3.0},
            "be":  {"amount": 0.8, "harmonics": 3.2, "scope": 60},
            "max": {"threshold": -9.0, "release": 55},
            "lim": {"threshold": -1.6},
        },
    },
    {
        "name": "Dynamics - Soft Volume Lift",
        "chain": "C",
        "gains": (1.5, 2.5, 3.0, 2.5, 1.5, 0.8, 0.3, 0.0, 0.3, 0.5,
                  0.8, 1.2, 1.8, 1.5, 1.0, 0.3, -0.3),
        "dyn": {
            "bl":  {"loudness": 0.0, "output": -3.0, "link": -5.0},
            "be":  {"amount": 1.0, "harmonics": 3.6, "scope": 66},
            "max": {"threshold": -7.5, "release": 42},
            "lim": {"threshold": -1.3},
        },
    },
]


# ──────────────────────────────────────────────────────────────────────
# Driver
# ──────────────────────────────────────────────────────────────────────

def main() -> int:
    here = Path(__file__).resolve().parent
    default_out = here.parent / "src" / "projectpulsewire" / "presets"

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    parser.add_argument("--out", type=Path, default=default_out,
                        help=f"Output directory (default: {default_out})")
    parser.add_argument("--check", action="store_true",
                        help="Validate only; do not write files.")
    args = parser.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)

    # Sanity check: 47 presets, no duplicates, all gains lengths match BANDS.
    seen: set[str] = set()
    for v in VOICINGS:
        assert v["name"] not in seen, f"duplicate preset name: {v['name']}"
        seen.add(v["name"])
        assert len(v["gains"]) == len(BANDS), (
            f"{v['name']}: expected {len(BANDS)} gain values, got {len(v['gains'])}"
        )
        assert v["chain"] in {"A", "B", "C"}, f"{v['name']}: bad chain"
    assert len(VOICINGS) == 47, f"expected 47 presets, got {len(VOICINGS)}"
    print(f"voicings OK: {len(VOICINGS)} presets, all 17 bands, no duplicates")

    if args.check:
        return 0

    written = 0
    for v in VOICINGS:
        data = assemble(v["gains"], v["chain"], v.get("dyn", {}))
        # Quick clip sanity: peak of |gain| should not exceed 6 dB after our
        # tuning — flag anything wilder for review (not fatal).
        peak = max(abs(g) for g in v["gains"])
        if peak > 6.0:
            print(f"  warn: {v['name']} peak gain {peak:+.1f} dB > 6 dB")
        path = args.out / f"{v['name']}.json"
        path.write_text(json.dumps(data, indent=4) + "\n", encoding="utf-8")
        written += 1
    print(f"wrote {written} presets to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
