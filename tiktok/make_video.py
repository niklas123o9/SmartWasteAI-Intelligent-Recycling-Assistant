#!/usr/bin/env python3
"""TikTok-Video-Generator v2: schnelle Schnitte, Emojis, Beat & Soundeffekte.

    python3 tiktok/make_video.py tiktok/scripts/02_gelb_oder_rest.json
    python3 tiktok/make_video.py skript.json --music song.mp3   # eigene Musik statt Beat
    python3 tiktok/make_video.py skript.json --no-beat          # nur Soundeffekte (für TikTok-Sounds)

Benötigt: Python 3, Pillow, numpy, ffmpeg (für Emojis: Noto Color Emoji).
Formatierung im Text: *Wort* = hervorgehoben (farbige Box). Emojis gehen überall.
"""
import argparse
import json
import math
import os
import random
import re
import subprocess
import sys
import wave

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H, FPS, SR = 1080, 1920, 30, 44100
MX = 90                      # seitlicher Rand
SAFE_TOP, SAFE_BOTTOM = 300, 1460
GREEN, RED = (34, 197, 94), (239, 68, 68)

HERE = os.path.dirname(os.path.abspath(__file__))
FONT_DIRS = [os.path.join(HERE, "fonts"), "/usr/share/fonts/opentype/inter",
             "/usr/share/fonts/truetype/dejavu", "/usr/share/fonts/truetype/noto",
             "/Library/Fonts", "/System/Library/Fonts", "C:/Windows/Fonts"]
FONT_FILES = {
    "black": ["Inter-Black.otf", "Inter-ExtraBold.otf", "DejaVuSans-Bold.ttf", "arialbd.ttf"],
    "bold": ["Inter-Bold.otf", "DejaVuSans-Bold.ttf", "arialbd.ttf"],
    "emoji": ["NotoColorEmoji.ttf", "Apple Color Emoji.ttc", "seguiemj.ttf"],
}
_cache = {}


def find_font(kind):
    for d in FONT_DIRS:
        for f in FONT_FILES[kind]:
            if os.path.exists(os.path.join(d, f)):
                return os.path.join(d, f)
    return None


def font(kind, size):
    key = ("f", kind, size)
    if key not in _cache:
        p = find_font(kind)
        _cache[key] = ImageFont.truetype(p, size) if p else ImageFont.load_default(size)
    return _cache[key]


def rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def ease_out(t):
    return 1 - (1 - clamp(t)) ** 3


def ease_back(t):
    t = clamp(t) - 1
    return 1 + 2.7 * t ** 3 + 1.7 * t ** 2


def is_emoji(ch):
    cp = ord(ch)
    return cp >= 0x1F000 or 0x2600 <= cp <= 0x27BF or cp in (0x2B50, 0x2B55, 0xFE0F, 0x200D, 0x203C, 0x2049)


# ---------- Grafik-Bausteine ----------

def emoji_img(e, size):
    key = ("e", e, size)
    if key not in _cache:
        p = find_font("emoji")
        if not p:
            _cache[key] = Image.new("RGBA", (1, 1))
            return _cache[key]
        f = ImageFont.truetype(p, 109)
        im = Image.new("RGBA", (180, 160), (0, 0, 0, 0))
        ImageDraw.Draw(im).text((10, 10), e, font=f, embedded_color=True)
        im = im.crop(im.getbbox() or (0, 0, 1, 1))
        s = size / max(im.size)
        _cache[key] = im.resize((max(1, int(im.width * s)), max(1, int(im.height * s))), Image.LANCZOS)
    return _cache[key]


def runs(word):
    """Teilt ein Wort in Text- und Emoji-Abschnitte."""
    out = []
    for ch in word:
        kind = "e" if is_emoji(ch) else "t"
        if out and out[-1][0] == kind:
            out[-1][1] += ch
        else:
            out.append([kind, ch])
    return out


def word_img(word, size, style, C):
    """style: normal | box (Akzent-Box) | active (Akzentfarbe) | dark"""
    key = ("w", word, size, style)
    if key in _cache:
        return _cache[key]
    f = font("black", size)
    stroke = max(4, size // 11)
    parts = []
    for kind, txt in runs(word):
        if kind == "e":
            parts.append(emoji_img(txt.replace("\ufe0f", "").replace("\u200d", "") or txt, int(size * 1.05)))
        else:
            l, t, r, b = f.getbbox(txt, stroke_width=stroke)
            asc, desc = f.getmetrics()
            im = Image.new("RGBA", (int(r - l + 4), asc + desc + 2 * stroke), (0, 0, 0, 0))
            d = ImageDraw.Draw(im)
            if style == "box":
                d.text((-l + 2, stroke), txt, font=f, fill=C["accent_text"])
            elif style == "dark":
                d.text((-l + 2, stroke), txt, font=f, fill=(20, 20, 20))
            else:
                fill = C["active"] if style == "active" else C["text"]
                d.text((-l + 2, stroke), txt, font=f, fill=fill, stroke_width=stroke, stroke_fill=(0, 0, 0))
            parts.append(im)
    w = sum(p.width for p in parts) + 4 * (len(parts) - 1)
    h = max(p.height for p in parts)
    pad = int(size * 0.22) if style == "box" else 0
    im = Image.new("RGBA", (w + 2 * pad, h + pad), (0, 0, 0, 0))
    if style == "box":
        ImageDraw.Draw(im).rounded_rectangle([0, pad * 0.3, w + 2 * pad, h + pad * 0.7], radius=int(size * 0.2),
                                             fill=C["accent"])
    x = pad
    for p in parts:
        im.alpha_composite(p, (x, (h - p.height) // 2 + pad // 2))
        x += p.width + 4
    _cache[key] = im
    return im


def parse(text):
    """'*Red Flags*, die' -> [('Red Flags,', True), ('die', False)]  (Markierung hält Wörter zusammen)"""
    out = []
    for line in text.split("\n"):
        span = None
        for w in line.split():
            if span is not None:
                span.append(w)
                if "*" in w:
                    out.append((" ".join(span).replace("*", ""), True)); span = None
            elif w.count("*") == 1 and w.startswith("*"):
                span = [w]
            else:
                out.append((w.replace("*", ""), "*" in w))
        if span:
            out.append((" ".join(span).replace("*", ""), True))
        out.append(("\n", False))
    return out[:-1]


def layout(words, size, C, max_w=W - 2 * MX, style_fn=None):
    """Bricht Wörter um und liefert [(img, cx, cy)] relativ zu y=0 plus Gesamthöhe."""
    gap = size * 0.16
    lines, cur, cw = [], [], 0
    for i, (w, hl) in enumerate(words):
        if w == "\n":
            lines.append(cur); cur, cw = [], 0
            continue
        im = word_img(w, size, style_fn(i, hl) if style_fn else ("box" if hl else "normal"), C)
        if cur and cw + gap + im.width > max_w:
            lines.append(cur); cur, cw = [], 0
        cur.append((i, im))
        cw += (gap if cw else 0) + im.width
    if cur:
        lines.append(cur)
    lh = size * 1.22
    placed = []
    for li, line in enumerate(lines):
        lw = sum(im.width for _, im in line) + gap * (len(line) - 1)
        x = (W - lw) / 2
        for i, im in line:
            placed.append((i, im, x + im.width / 2, li * lh + lh / 2))
            x += im.width + gap
    widest = max((sum(im.width for _, im in l) + gap * (len(l) - 1) for l in lines), default=0)
    return placed, len(lines) * lh, widest


def fit(words, size, C, max_h, max_lines=4):
    while size > 40:
        placed, h, widest = layout(words, size, C)
        if h <= max_h and widest <= W - 2 * MX and h <= max_lines * size * 1.22 + 1:
            return size, placed, h
        size -= 6
    placed, h, _ = layout(words, size, C)
    return size, placed, h


def composite(dst, im, x, y):
    """alpha_composite, das Bilder am Rand sauber abschneidet."""
    x0, y0 = max(0, x), max(0, y)
    x1, y1 = min(dst.width, x + im.width), min(dst.height, y + im.height)
    if x1 <= x0 or y1 <= y0:
        return
    if (x0, y0, x1, y1) != (x, y, x + im.width, y + im.height):
        im = im.crop((x0 - x, y0 - y, x1 - x, y1 - y))
    dst.alpha_composite(im, (x0, y0))


def paste_scaled(dst, im, cx, cy, scale=1.0, alpha=1.0, angle=0.0):
    if scale <= 0.01 or alpha <= 0.01:
        return
    if abs(scale - 1) > 0.01:
        im = im.resize((max(1, int(im.width * scale)), max(1, int(im.height * scale))), Image.BILINEAR)
    if angle:
        im = im.rotate(angle, resample=Image.BICUBIC, expand=True)
    if alpha < 0.99:
        im = im.copy()
        im.putalpha(im.getchannel("A").point(lambda v: int(v * alpha)))
    x, y = int(cx - im.width / 2), int(cy - im.height / 2)
    composite(dst, im, x, y)


def stamp(t, start, dur=0.16):
    """Wort 'knallt' rein: von groß auf normal."""
    k = (t - start) / dur
    if k <= 0:
        return 0, 0
    return 1 + 0.9 * (1 - ease_out(k)), clamp(k * 2)


def draw_words(ov, placed, top, t, start, per_word, pop=True):
    for i, im, cx, cy in placed:
        s, a = stamp(t, start + i * per_word) if pop else (1, 1)
        paste_scaled(ov, im, cx, top + cy, s, a)


def pill(d, cx, cy, text, size, fill, tcol, pad=(34, 16)):
    f = font("black", size)
    tw = f.getlength(text)
    asc, desc = f.getmetrics()
    d.rounded_rectangle([cx - tw / 2 - pad[0], cy - asc / 2 - pad[1], cx + tw / 2 + pad[0], cy + asc / 2 + pad[1] + 6],
                        radius=999, fill=fill)
    d.text((cx - tw / 2, cy - asc / 2 - 2), text, font=f, fill=tcol)


# ---------- Hintergrund ----------

class Background:
    def __init__(self, C, emojis, seed=7):
        self.C = C
        self.grads = {}
        rnd = random.Random(seed)
        self.parts = [dict(e=rnd.choice(emojis), x=rnd.uniform(0, W), y=rnd.uniform(0, H + 300),
                           sp=rnd.uniform(50, 130), size=rnd.randint(90, 170), ph=rnd.uniform(0, 6.3))
                      for _ in range(14)] if emojis else []
        for p in self.parts:
            im = emoji_img(p["e"], p["size"]).copy()
            im.putalpha(im.getchannel("A").point(lambda v: int(v * 0.33)))
            p["im"] = im

    def grad(self, c1, c2):
        if (c1, c2) not in self.grads:
            a, b = np.array(rgb(c1), float), np.array(rgb(c2), float)
            t = np.linspace(0, 1, H)[:, None]
            col = (a + (b - a) * t).astype(np.uint8)
            self.grads[(c1, c2)] = Image.fromarray(np.repeat(col[:, None, :], W, axis=1).reshape(H, W, 3)).convert("RGBA")
        return self.grads[(c1, c2)]

    def render(self, T, bg, beat, rays=0.0):
        img = self.grad(*bg).copy()
        # Glow, der im Beat pulsiert, und rotierende Strahlen
        sw, sh = W // 8, H // 8
        small = Image.new("RGBA", (sw, sh), (0, 0, 0, 0))
        d = ImageDraw.Draw(small)
        pulse = math.exp(-((T % beat) / beat) * 4)
        r = sw * (0.55 + 0.12 * pulse)
        cx, cy = sw / 2 + math.sin(T * 0.7) * 20, sh * 0.45 + math.cos(T * 0.5) * 30
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=self.C["glow"] + (int(70 + 70 * pulse),))
        if rays > 0:
            n, R = 14, sh * 1.2
            for k in range(n):
                a0 = T * 0.6 + k * 2 * math.pi / n
                a1 = a0 + math.pi / n * 0.55
                d.polygon([(cx, cy), (cx + R * math.cos(a0), cy + R * math.sin(a0)),
                           (cx + R * math.cos(a1), cy + R * math.sin(a1))],
                          fill=(255, 255, 255, int(22 * rays)))
        small = small.filter(ImageFilter.GaussianBlur(5))
        img.alpha_composite(small.resize((W, H), Image.BICUBIC))
        for p in self.parts:
            y = (p["y"] - p["sp"] * T) % (H + 300) - 150
            x = p["x"] + math.sin(T * 0.8 + p["ph"]) * 40
            paste_scaled(img, p["im"], x, y, angle=math.sin(T * 1.1 + p["ph"]) * 18)
        return img


# ---------- Szenen ----------

def dur_of(sc):
    tp = sc.get("type")
    if "duration" in sc:
        return sc["duration"]
    if tp == "quiz":
        return sc.get("think", 2.6) + sc.get("reveal", 1.7)
    if tp == "scan":
        return sc.get("think", 2.2) + sc.get("reveal", 1.8)
    if tp == "captions":
        return 0.3 + len([w for w, _ in parse(sc["text"]) if w != "\n"]) * sc.get("per_word", 0.3)
    return {"hook": 2.4, "punch": 1.1, "cta": 3.0}.get(tp, 2.5)


def bouncing_emoji(ov, e, size, cx, cy, t, start=0.0, bounce=True):
    if not e:
        return
    k = (t - start) / 0.3
    if k <= 0:
        return
    s = ease_back(k)
    dy = -abs(math.sin(t * 5)) * 30 if bounce and k > 1 else 0
    paste_scaled(ov, emoji_img(e, size), cx, cy + dy, s, clamp(k * 2), math.sin(t * 3) * 6)


def s_hook(ov, sc, t, d, C, ev):
    words = parse(sc["text"])
    has_e = bool(sc.get("emoji"))
    size, placed, h = fit(words, sc.get("size", 124), C, 620)
    top = (1060 if has_e else 880) - h / 2
    bouncing_emoji(ov, sc.get("emoji"), 300, W / 2, top - 230, t)
    pw = min(0.16, (d * 0.45) / max(1, len(placed)))
    draw_words(ov, placed, top, t, 0.12, pw)
    if sc.get("sub"):
        sw = parse(sc["sub"])
        _, sp, _ = fit(sw, 58, C, 200)
        draw_words(ov, sp, top + h + 40, t, 0.4 + len(placed) * pw, 0.05)


def s_punch(ov, sc, t, d, C, ev):
    words = parse(sc["text"])
    size, placed, h = fit(words, sc.get("size", 170), C, 700, 3)
    top = 930 - h / 2
    bouncing_emoji(ov, sc.get("emoji"), 260, W / 2, top - 200, t)
    draw_words(ov, placed, top, t, 0.0, 0.07)


def s_captions(ov, sc, t, d, C, ev):
    words = [(w, hl) for w, hl in parse(sc["text"]) if w != "\n"]
    pw = (d - 0.3) / max(1, len(words))
    size = sc.get("size", 118)
    # Wörter in Häppchen von max. 3 Wörtern aufteilen (wie CapCut-Untertitel)
    chunks, cur = [], []
    for i, (w, hl) in enumerate(words):
        cur.append(i)
        end = w.endswith((".", "!", "?", ":", ","))
        if len(cur) == 3 or end or sum(word_img(words[j][0], size, "normal", C).width for j in cur) > W - 2 * MX - 200:
            chunks.append(cur); cur = []
    if cur:
        chunks.append(cur)
    wt = sc.get("_wt")
    if wt:
        idx = max([i for i, x in enumerate(wt) if x <= t] or [0])
    else:
        idx = min(int(t / pw), len(words) - 1)
    chunk = next(c for c in chunks if idx <= c[-1])
    active = idx
    sub = [words[j] for j in chunk]

    def style(i, hl):
        j = chunk[i]
        return "box" if hl else ("active" if j == active else "normal")

    placed, h, _ = layout(sub, size, C, style_fn=style)
    cstart = wt[chunk[0]] if wt else chunk[0] * pw
    k = (t - cstart) / 0.12
    s = 0.85 + 0.15 * ease_back(k)
    top = (1050 if sc.get("emoji") else 900) - h / 2
    bouncing_emoji(ov, sc.get("emoji"), 240, W / 2, top - 200, t)
    for i, im, cx, cy in placed:
        paste_scaled(ov, im, cx, top + cy, s * (1.08 if chunk[i] == active else 1), clamp(k * 3))


def s_quiz(ov, sc, t, d, C, ev):
    think = sc.get("think", 2.6)
    dr = ImageDraw.Draw(ov)
    if sc.get("_label"):
        k = ease_back(t / 0.25)
        if k > 0.3:
            pill(dr, W / 2, SAFE_TOP + 40, sc["_label"], 44, (0, 0, 0, 150), (255, 255, 255, 255))
    bouncing_emoji(ov, sc.get("emoji"), 330, W / 2, 640, t)
    name = parse(sc["item"])
    _, placed, h = fit(name, 100, C, 260, 2)
    draw_words(ov, placed, 900 - h / 2, t, 0.15, 0.06)
    opts = sc["options"]
    revealed = t >= think
    for i, o in enumerate(opts):
        cx = W / 2 + (i - (len(opts) - 1) / 2) * 470
        cy = 1180
        k = ease_back((t - 0.35 - i * 0.12) / 0.3)
        if k <= 0:
            continue
        correct = i == sc["answer"]
        fill, tcol, sc_ = (255, 255, 255, 240), (20, 20, 20, 255), k
        if revealed:
            rk = ease_back((t - think) / 0.25)
            if correct:
                fill, tcol = GREEN + (255,), (255, 255, 255, 255)
                sc_ = 1 + 0.15 * rk
            else:
                fill, tcol = RED + (200,), (255, 255, 255, 220)
                cx += math.sin((t - think) * 60) * 14 * max(0, 1 - (t - think) / 0.4)
                sc_ = 1 - 0.1 * rk
        f = font("black", int(54 * sc_))
        label = o + ("  ✓" if revealed and correct else "")
        tw = f.getlength(label)
        bw, bh = max(tw + 70, 380 * sc_), 130 * sc_
        dr.rounded_rectangle([cx - bw / 2, cy - bh / 2, cx + bw / 2, cy + bh / 2], radius=40, fill=fill,
                             outline=(0, 0, 0, 255), width=6)
        asc, _ = f.getmetrics()
        dr.text((cx - tw / 2, cy - asc / 2 - 4), label, font=f, fill=tcol)
    if not revealed:
        # Countdown-Ring
        remain = think - t
        n = math.ceil(remain)
        frac = remain - (n - 1)
        cx, cy, r = W / 2, 1360, 62
        dr.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(0, 0, 0, 140))
        dr.arc([cx - r, cy - r, cx + r, cy + r], -90, -90 + 360 * frac, fill=C["accent"] + (255,), width=12)
        f = font("black", 64)
        dr.text((cx - f.getlength(str(n)) / 2, cy - 40), str(n), font=f, fill=(255, 255, 255, 255))
    else:
        if sc.get("fact"):
            words = parse(sc["fact"])
            _, placed, h = fit(words, 60, C, 200, 2)
            draw_words(ov, placed, 1340 - h / 2 + 30, t, think + 0.25, 0.04)
        rk = (t - think) / 0.3
        paste_scaled(ov, emoji_img("✅", 200), W / 2 + 220, 560, 1 + 1.2 * (1 - ease_out(rk)), clamp(rk * 2), -12)


def s_cta(ov, sc, t, d, C, ev):
    words = parse(sc["text"])
    size, placed, h = fit(words, sc.get("size", 120), C, 520)
    top = 980 - h / 2
    bouncing_emoji(ov, sc.get("emoji"), 260, W / 2, top - 210, t)
    draw_words(ov, placed, top, t, 0.1, 0.1)
    if sc.get("sub"):
        k = ease_back((t - 0.9) / 0.35)
        if k > 0:
            dr = ImageDraw.Draw(ov)
            pulse = 1 + 0.04 * math.sin(t * 7)
            f = font("black", 56)
            tw = f.getlength(sc["sub"])
            bw, bh = (tw + 100) * k * pulse, 124 * k * pulse
            cy = top + h + 140
            dr.rounded_rectangle([W / 2 - bw / 2, cy - bh / 2, W / 2 + bw / 2, cy + bh / 2], radius=62,
                                 fill=C["accent"])
            if k > 0.8:
                asc, _ = f.getmetrics()
                dr.text((W / 2 - tw / 2, cy - asc / 2 - 4), sc["sub"], font=f, fill=C["accent_text"])


BINS = {  # Farbe, Textfarbe
    "gelb": ((250, 204, 21), (20, 20, 20)), "rest": ((55, 65, 81), (255, 255, 255)),
    "papier": ((37, 99, 235), (255, 255, 255)), "bio": ((146, 64, 14), (255, 255, 255)),
    "glas": ((22, 163, 74), (255, 255, 255)), "pfand": ((14, 165, 233), (255, 255, 255)),
}


def s_scan(ov, sc, t, d, C, ev):
    """KI-Scanner: Sucher-Rahmen, Scan-Linie, Ladebalken, dann Ergebnis."""
    think = sc.get("think", 2.2)
    dr = ImageDraw.Draw(ov)
    if sc.get("_label"):
        pill(dr, W / 2, SAFE_TOP + 40, sc["_label"], 44, (0, 0, 0, 150), (255, 255, 255, 255))
    cx, cy, half = W / 2, 690, 250
    k = ease_back(t / 0.3)
    hh = half * k
    L, col = 70, C["accent"] + (255,)
    for sx in (-1, 1):
        for sy in (-1, 1):
            x0, y0 = cx + sx * hh, cy + sy * hh
            dr.line([(x0, y0), (x0 - sx * L, y0)], fill=col, width=12)
            dr.line([(x0, y0), (x0, y0 - sy * L)], fill=col, width=12)
    paste_scaled(ov, emoji_img(sc["emoji"], 300), cx, cy + math.sin(t * 3) * 8, k, clamp(t * 4), math.sin(t * 2) * 4)
    name = parse(sc["item"])
    _, placed, h = fit(name, 92, C, 240, 2)
    draw_words(ov, placed, 1030 - h / 2, t, 0.15, 0.05)
    if t < think:
        # Scan-Linie fährt hoch und runter
        ly = cy + math.sin(t * 4.2) * half * 0.9
        glow = Image.new("RGBA", (int(2 * half), 60), (0, 0, 0, 0))
        g = ImageDraw.Draw(glow)
        for j in range(30):
            g.line([(0, 30 - j), (2 * half, 30 - j)], fill=C["accent"] + (int(90 * (1 - j / 30)),))
            g.line([(0, 30 + j), (2 * half, 30 + j)], fill=C["accent"] + (int(90 * (1 - j / 30)),))
        composite(ov, glow, int(cx - half), int(ly - 30))
        dr.line([(cx - half, ly), (cx + half, ly)], fill=(255, 255, 255, 255), width=5)
        p = clamp(ease_out(t / (think * 0.95)))
        bw, by = 760, 1210
        dr.rounded_rectangle([cx - bw / 2, by - 26, cx + bw / 2, by + 26], radius=26, fill=(0, 0, 0, 150))
        dr.rounded_rectangle([cx - bw / 2, by - 26, cx - bw / 2 + max(52, bw * p), by + 26], radius=26, fill=col)
        f = font("bold", 46)
        dots = "." * (1 + int(t * 4) % 3)
        txt = f"KI analysiert{dots}  {int(p * 100)} %"
        dr.text((cx - bw / 2, by + 50), txt, font=f, fill=(255, 255, 255, 230))
    else:
        rt = t - think
        bcol, tcol = BINS.get(sc.get("bin", "rest"), BINS["rest"])
        rk = ease_back(rt / 0.3)
        f = font("black", 76)
        txt = sc["result"]
        tw = f.getlength(txt)
        bw, bh = (tw + 120) * rk, 150 * rk
        by = 1220
        if rk > 0.05:
            dr.rounded_rectangle([cx - bw / 2, by - bh / 2, cx + bw / 2, by + bh / 2], radius=46,
                                 fill=bcol + (255,), outline=(0, 0, 0, 255), width=7)
        if rk > 0.8:
            asc, _ = f.getmetrics()
            dr.text((cx - tw / 2, by - asc / 2 - 6), txt, font=f, fill=tcol + (255,))
        if sc.get("confidence"):
            fs = font("bold", 42)
            ct = f"Sicherheit: {sc['confidence']} %"
            dr.text((cx - fs.getlength(ct) / 2, by + 88), ct, font=fs, fill=(255, 255, 255, int(220 * clamp(rt * 3))))
        if sc.get("fact"):
            _, fp, fh = fit(parse(sc["fact"]), 58, C, 180, 2)
            draw_words(ov, fp, 1445 - fh / 2, t, think + 0.3, 0.04)
        paste_scaled(ov, emoji_img(sc.get("stamp", "✅"), 190), cx + 230, cy - 210,
                     1 + 1.2 * (1 - ease_out(rt / 0.3)), clamp(rt * 6), -12)


SCENES = {"hook": s_hook, "punch": s_punch, "captions": s_captions, "quiz": s_quiz, "cta": s_cta, "scan": s_scan}


# ---------- Sprachausgabe (Piper, offline) ----------

PRONOUNCE = {"SmartWasteAI": "Smart Wehst I Ei", "Red Flags": "Rädd Fläggs", "Red Flag": "Rädd Fläck",
             "Score": "Skohr", "Tetra Pak": "Tetra Pack", "Kommis": "Kommis"}
LEAD = 0.12  # Sprechbeginn nach dem Schnitt


def speech_text(text, extra=None):
    s = "".join(ch for ch in text.replace("*", "") if not is_emoji(ch))
    for a, b in {**PRONOUNCE, **(extra or {})}.items():
        s = s.replace(a, b)
    s = re.sub(r"(\d+)\s*/\s*(\d+)", r"\1 von \2", s)
    s = s.replace("&", " und ").replace("+", " plus ").replace("=", " ist ").replace("·", ",").replace("…", "...")
    s = re.sub(r"\s+", " ", s).strip()
    return s if not s or s[-1] in ".!?:," else s + "."


class Voice:
    def __init__(self, path, speed=0.92):
        from piper import PiperVoice, SynthesisConfig
        self.v = PiperVoice.load(path)
        self.sr = self.v.config.sample_rate
        orig = self.v.phonemize

        def fixed(text):  # neuere espeak-Versionen zerlegen "ç" (ich-Laut) in c + Cedille
            out = []
            for sent in orig(text):
                m = []
                for ph in sent:
                    if ph == "̧":
                        if m and m[-1] == "c":
                            m[-1] = "ç"
                        continue
                    m.append(ph)
                out.append(m)
            return out

        self.v.phonemize = fixed
        self.cfg = SynthesisConfig(length_scale=speed, noise_scale=0.6, noise_w_scale=0.7)

    def say(self, text):
        gap = np.zeros(int(self.sr * 0.07), np.float32)
        parts = []
        for c in self.v.synthesize(text, syn_config=self.cfg):
            parts += [c.audio_float_array, gap]
        a = np.concatenate(parts) if parts else np.zeros(1, np.float32)
        loud = np.where(np.abs(a) > 0.02)[0]
        return a[max(0, loud[0] - 160):loud[-1] + 800] if len(loud) else a


def plan_voice(scenes, voice, extra):
    """Spricht die Bildschirmtexte, passt Szenenlängen an und liefert [(Startzeit, Audio)]."""
    clips, T0 = [], 0.0
    for sc in scenes:
        tp = sc.get("type")
        say = lambda txt: voice.say(speech_text(txt, extra))
        L = lambda a: len(a) / voice.sr
        if tp in ("quiz", "scan"):
            if tp == "quiz":
                o = sc["options"]
                q = sc.get("say", f"{sc['item']}: {o[0]} oder {o[1]}?")
                a_txt = sc.get("say_reveal", f"{o[sc['answer']]}! {sc.get('fact', '')}")
                base_think, base_rev, wait = 2.6, 1.7, 1.2
            else:
                q = sc.get("say", sc["item"])
                a_txt = sc.get("say_reveal", f"{sc['result']}! {sc.get('fact', '')}")
                base_think, base_rev, wait = 2.2, 1.8, 0.9
            qa, aa = say(q), say(a_txt)
            sc["think"] = max(sc.get("think", base_think), LEAD + L(qa) + wait)
            sc["reveal"] = max(sc.get("reveal", base_rev), 0.12 + L(aa) + 0.35)
            sc.pop("duration", None)
            clips += [(T0 + LEAD, qa), (T0 + sc["think"] + 0.12, aa)]
        else:
            text = sc.get("say") or (sc["text"] + (" " + sc["sub"] if sc.get("sub") else ""))
            if tp == "hook" and sc.get("sub") and not sc.get("say"):
                text = sc["text"].rstrip() + ("" if sc["text"].rstrip()[-1:] in ".!?" else ".") + " " + sc["sub"]
            a = say(text)
            tail = {"captions": 0.25, "punch": 0.2, "hook": 0.35, "cta": 0.9}.get(tp, 0.3)
            vis = sc.get("duration", {"hook": 1.6, "punch": 1.0, "cta": 2.6}.get(tp, 1.0))
            sc["duration"] = max(vis, LEAD + L(a) + tail)
            clips.append((T0 + LEAD, a))
            if tp == "captions":  # Karaoke-Timing grob an die Sprache koppeln
                words = [w for w, _ in parse(sc["text"]) if w != "\n"]
                wts = [len(w) + 2 + (4 if w.endswith((".", "!", "?", ",", ":")) else 0) for w in words]
                tot, acc, starts = sum(wts), 0, []
                for wgt in wts:
                    starts.append(LEAD + L(a) * acc / tot)
                    acc += wgt
                sc["_wt"] = starts
        T0 += dur_of(sc)
    return clips


def voice_bus(clips, sr, total):
    """Legt die Sprachclips auf eine Spur und veredelt sie (EQ, Kompressor) auf 44,1 kHz."""
    bus = np.zeros(int((total + 1) * sr), np.float32)
    for at, a in clips:
        i = int(at * sr)
        j = min(len(bus), i + len(a))
        bus[i:j] += a[:j - i]
    pcm = (np.clip(bus / (np.max(np.abs(bus)) or 1) * 0.9, -1, 1) * 32767).astype(np.int16).tobytes()
    af = ("highpass=f=75,equalizer=f=250:t=q:w=1:g=-2,equalizer=f=3200:t=q:w=1.2:g=3,"
          "acompressor=threshold=-20dB:ratio=3:attack=5:release=60:makeup=2,aresample=%d" % SR)
    raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-f", "s16le", "-ar", str(sr), "-ac", "1", "-i", "-",
                          "-af", af, "-f", "f32le", "-ac", "1", "-"], input=pcm, capture_output=True).stdout
    return np.frombuffer(raw, np.float32).astype(float)


# ---------- Audio ----------

def synth_audio(total, events, bpm, beat_on, music=None, music_volume=0.6, voice=None):
    n = int(total * SR) + SR
    mix = np.zeros(n)
    tt = lambda d: np.arange(int(d * SR)) / SR
    rng = np.random.default_rng(1)

    def add(sig, at, vol=1.0):
        i = int(at * SR)
        j = min(n, i + len(sig))
        if i < n:
            mix[i:j] += sig[:j - i] * vol

    def kick():
        x = tt(0.35)
        f = 45 + 110 * np.exp(-x * 30)
        return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-x * 9)

    def noise(d, decay):
        x = tt(d)
        return rng.uniform(-1, 1, len(x)) * np.exp(-x * decay)

    def hat():
        s = noise(0.05, 90)
        return np.diff(s, prepend=0)

    def tone(freqs, d, decay, wave_="sin"):
        x = tt(d)
        s = sum(np.sin(2 * np.pi * f * x) for f in freqs) / len(freqs)
        return s * np.exp(-x * decay) * np.minimum(1, x * 200)

    if music:
        raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-stream_loop", "-1", "-i", music, "-t", str(total + 1),
                              "-f", "f32le", "-ac", "1", "-ar", str(SR), "-"], capture_output=True).stdout
        m = np.frombuffer(raw, np.float32).astype(float)
        mix[:min(n, len(m))] += m[:n] * music_volume
    elif beat_on:
        beat = 60 / bpm
        roots = [55.0, 43.65, 65.41, 49.0]          # A, F, C, G
        chords = [[220, 261.6, 329.6], [174.6, 220, 261.6], [261.6, 329.6, 392], [196, 246.9, 293.7]]
        b = 0
        while b * beat < total:
            at = b * beat
            bar = (b // 4) % 4
            add(kick(), at, 0.9 if b % 2 == 0 else 0.55)
            if b % 4 in (1, 3):
                add(noise(0.18, 22), at, 0.28)
            add(hat(), at + beat / 2, 0.22)
            add(hat(), at + beat * 0.75, 0.10)
            add(tone([roots[bar]], beat * 0.9, 4), at, 0.55)
            if b % 4 == 0:
                x = tt(beat * 4)
                pad = sum(np.sin(2 * np.pi * f * x) + 0.3 * np.sin(4 * np.pi * f * x) for f in chords[bar])
                pad *= np.minimum(1, x * 3) * np.minimum(1, (beat * 4 - x) * 4) / 3
                add(pad, at, 0.10)
            b += 1
        mix[:n] *= np.minimum(1, np.arange(n) / (SR * 0.05))
    music = mix.copy()
    mix[:] = 0

    for kind, at in events:
        if kind == "whoosh":
            x = tt(0.35)
            s = np.diff(rng.uniform(-1, 1, len(x)), prepend=0) * np.sin(np.pi * x / 0.35) ** 2
            add(s, max(0, at - 0.15), 0.35)
        elif kind == "impact":
            x = tt(0.6)
            s = np.sin(2 * np.pi * (40 + 80 * np.exp(-x * 20)) * x) * np.exp(-x * 6) + noise(0.6, 25) * 0.4
            add(s, at, 0.8)
        elif kind == "pop":
            x = tt(0.08)
            add(np.sin(2 * np.pi * (500 + 2500 * x) * x) * np.exp(-x * 50), at, 0.35)
        elif kind == "blip":
            add(tone([2400], 0.04, 120), at, 0.18)
        elif kind == "tick":
            add(tone([1800], 0.05, 80), at, 0.4)
        elif kind == "ding":
            add(tone([1046.5, 1568], 0.8, 5), at, 0.45)
            add(tone([1318.5, 2093], 0.6, 6), at + 0.09, 0.35)
    norm = lambda a, lvl: a / (np.max(np.abs(a)) or 1) * lvl
    music, sfx = norm(music, 0.5), norm(mix, 0.55)
    out = music + sfx
    if voice is not None and len(voice):
        v = np.zeros(n)
        v[:min(n, len(voice))] = voice[:n]
        # Ducking: Musik wird leiser, solange gesprochen wird
        win = int(SR * 0.05)
        env = np.sqrt(np.convolve(v ** 2, np.ones(win) / win, "same"))
        env = np.clip(env / 0.03, 0, 1)
        env = np.convolve(env, np.ones(int(SR * 0.25)) / int(SR * 0.25), "same")
        env = np.clip(env * 1.5, 0, 1)
        out = music * (1 - 0.65 * env) + sfx * (1 - 0.35 * env) + norm(v, 0.95)
    out = np.tanh(out * 1.1) * 0.95
    return (out * 32767).astype(np.int16)


# ---------- Rendern ----------

def render(script, out, music=None, beat_on=True, voice_path=None, speed=0.92):
    th = script.get("theme", {})
    C = {"text": rgb(th.get("text", "#ffffff")), "accent": rgb(th.get("accent", "#facc15")),
         "accent_text": rgb(th.get("accent_text", "#111111")), "glow": rgb(th.get("glow", th.get("accent", "#facc15"))),
         "active": rgb(th.get("active", th.get("accent", "#facc15")))}
    bgs = th.get("bgs", [th.get("bg", ["#4c1d95", "#0f0a1f"])])
    bpm = script.get("bpm", 128)
    beat = 60 / bpm
    scenes = script["scenes"]
    for tp_, word in (("quiz", "FRAGE"), ("scan", "SCAN")):
        group = [s for s in scenes if s.get("type") == tp_]
        for i, s in enumerate(group):
            s["_label"] = s.get("label", f"{word} {i + 1}/{len(group)}")
    clips, vsr = [], None
    if voice_path:
        v = Voice(voice_path, speed)
        vsr = v.sr
        clips = plan_voice(scenes, v, script.get("pronounce"))
    durs = [dur_of(s) for s in scenes]
    total = sum(durs)
    bg = Background(C, script.get("particles", []))

    # Sound-Events vorab planen
    events, T0 = [], 0.0
    for i, (sc, d) in enumerate(zip(scenes, durs)):
        tp = sc.get("type")
        events.append(("impact" if tp in ("hook", "punch") or i == 0 else "whoosh", T0))
        if tp == "quiz":
            think = sc.get("think", 2.6)
            for k in range(math.ceil(think)):
                events.append(("tick", T0 + think - math.ceil(think) + k))
            events.append(("ding", T0 + think))
        if tp == "scan":
            think = sc.get("think", 2.2)
            x = 0.3
            while x < think - 0.1:
                events.append(("blip", T0 + x)); x += 0.25
            events.append(("ding", T0 + think))
        if tp == "cta":
            events.append(("pop", T0 + 0.9))
        T0 += d

    wav = os.path.splitext(out)[0] + "_audio.wav"
    with wave.open(wav, "wb") as wf:
        wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(SR)
        vb = voice_bus(clips, vsr, total) if clips else None
        wf.writeframes(synth_audio(total, events, bpm, beat_on, music, voice=vb).tobytes())

    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
           "-r", str(FPS), "-i", "-", "-i", wav, "-map", "0:v", "-map", "1:a",
           "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-b:a", "192k", "-ac", "2", "-t", f"{total:.3f}", "-movflags", "+faststart", out]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    total_frames = int(total * FPS)
    header = script.get("header")
    fr, T0 = 0, 0.0
    for si, (sc, d) in enumerate(zip(scenes, durs)):
        tp = sc.get("type")
        sbg = sc.get("bg", bgs[si % len(bgs)])
        rays = 1.0 if tp in ("hook", "punch", "cta") else 0.0
        fn = SCENES[tp]
        for i in range(int(round(d * FPS))):
            t = i / FPS
            T = fr / FPS
            think = sc.get("think", 2.6 if tp == "quiz" else 2.2)
            quiz_rays = 1.0 if tp in ("quiz", "scan") and t >= think else 0.0
            img = bg.render(T, sbg, beat, max(rays, quiz_rays))
            ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            fn(ov, sc, t, d, C, events)
            # Kamera: Zoom-Punch beim Schnitt, Wackeln bei Impact, leichtes Atmen im Beat
            zoom = 1 + 0.10 * (1 - ease_out(t / 0.25)) + 0.012 * math.exp(-((T % beat) / beat) * 5)
            shake = 22 * max(0, 1 - t / 0.3) if tp in ("hook", "punch") else 0
            if tp in ("quiz", "scan") and 0 <= t - think < 0.3:
                shake = 14
            ox = math.sin(fr * 2.1) * shake
            oy = math.cos(fr * 2.7) * shake
            if zoom > 1.003 or shake:
                z = ov.resize((int(W * zoom), int(H * zoom)), Image.BILINEAR)
                l = int((z.width - W) / 2 + ox)
                tp_ = int((z.height - H) / 2 + oy)
                ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
                composite(ov, z, -l, -tp_)
            img.alpha_composite(ov)
            dr = ImageDraw.Draw(img)
            dr.rectangle([0, 0, W, 12], fill=(0, 0, 0, 90))
            dr.rectangle([0, 0, W * (fr + 1) / total_frames, 12], fill=C["accent"] + (255,))
            if header:
                hw = word_img(header, 58, "normal", C)
                paste_scaled(img, hw, W / 2, 200)
            frame = img.convert("RGB")
            if tp in ("hook", "punch") and t < 0.1:
                frame = Image.blend(frame, Image.new("RGB", (W, H), (255, 255, 255)), 0.55 * (1 - t / 0.1))
            proc.stdin.write(frame.tobytes())
            fr += 1
        T0 += d
        print(f"  Szene {si + 1}/{len(scenes)} ({tp}) fertig", file=sys.stderr)
    proc.stdin.close()
    ok = proc.wait() == 0
    os.remove(wav)
    if not ok:
        sys.exit("ffmpeg ist fehlgeschlagen")
    if script.get("caption"):
        with open(os.path.splitext(out)[0] + "_caption.txt", "w", encoding="utf-8") as f:
            f.write(script["caption"].strip() + "\n")
    print(f"Fertig: {out} ({total:.1f}s)")


def main():
    ap = argparse.ArgumentParser(description="Erstellt ein TikTok-Video aus einem JSON-Skript.")
    ap.add_argument("script")
    ap.add_argument("-o", "--out")
    ap.add_argument("--music", help="eigene Audiodatei statt des generierten Beats")
    ap.add_argument("--no-beat", action="store_true", help="nur Soundeffekte (Trend-Sound in TikTok hinzufügen)")
    ap.add_argument("--voice", help="Stimme: Name (thorsten, kerstin, ramona …) oder Pfad zu .onnx")
    ap.add_argument("--no-voice", action="store_true", help="ohne Vorlese-Stimme")
    ap.add_argument("--speed", type=float, default=None, help="Sprechtempo (<1 = schneller), Standard 0.92")
    a = ap.parse_args()
    with open(a.script, encoding="utf-8") as f:
        script = json.load(f)
    out = a.out or os.path.join(HERE, "output", os.path.splitext(os.path.basename(a.script))[0] + ".mp4")
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    voice_path = None
    if not a.no_voice and script.get("voice", "thorsten") != "none":
        name = a.voice or script.get("voice", "thorsten")
        voice_path = name if name.endswith(".onnx") else os.path.join(HERE, "voices", f"de-{name}-low.onnx")
        if not os.path.exists(voice_path):
            print(f"Stimme nicht gefunden: {voice_path} (tiktok/get_voices.sh ausführen). Ohne Stimme weiter.",
                  file=sys.stderr)
            voice_path = None
    render(script, out, a.music, not a.no_beat, voice_path, a.speed or script.get("speed", 0.92))


if __name__ == "__main__":
    main()
