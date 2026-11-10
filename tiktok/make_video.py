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
    return 1 + (0.15 if CLEAN.get("calm") else 0.9) * (1 - ease_out(k)), clamp(k * (1.2 if CLEAN.get("calm") else 2))


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

    def space(self, img, T):
        """Ruhiger Sternenhimmel: langsam ziehende Nebel + sanft funkelnde Sterne."""
        if not hasattr(self, "_neb"):
            rnd = random.Random(11)
            sw, sh = W // 4, H // 4
            neb = Image.new("RGBA", (sw + 80, sh + 80), (0, 0, 0, 0))
            dn = ImageDraw.Draw(neb)
            for col in [(124, 58, 237), (14, 165, 233), (236, 72, 153), (59, 130, 246), (147, 51, 234)]:
                for _ in range(2):
                    x, y, r = rnd.uniform(0, sw), rnd.uniform(0, sh), rnd.uniform(60, 130)
                    dn.ellipse([x - r, y - r * 0.6, x + r, y + r * 0.6], fill=col + (55,))
            self._neb = neb.filter(ImageFilter.GaussianBlur(28)).resize(((sw + 80) * 4, (sh + 80) * 4), Image.BICUBIC)
            self._stars = [(rnd.uniform(0, W), rnd.uniform(0, H), rnd.choice([1.5, 2, 2.5, 3.5]), rnd.uniform(0, 6.3),
                            rnd.uniform(0.6, 1.8)) for _ in range(170)]
        ox = int(160 + math.sin(T * 0.04) * 150)
        oy = int(160 + math.cos(T * 0.03) * 150)
        img.alpha_composite(self._neb.crop((ox, oy, ox + W, oy + H)))
        layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        for x, y, r, ph, sp in self._stars:
            a = int(110 + 120 * (0.5 + 0.5 * math.sin(T * sp + ph)))
            yy = (y + T * 4) % H  # ganz langsames Driften
            d.ellipse([x - r, yy - r, x + r, yy + r], fill=(255, 255, 255, a))
        img.alpha_composite(layer)
        return img

    def render(self, T, bg, beat, rays=0.0, calm=False, backdrop=None):
        img = self.grad(*bg).copy()
        if backdrop == "space":
            return self.space(img, T)
        # Glow, der im Beat pulsiert, und rotierende Strahlen
        sw, sh = W // 8, H // 8
        small = Image.new("RGBA", (sw, sh), (0, 0, 0, 0))
        d = ImageDraw.Draw(small)
        pulse = 0.3 if calm else math.exp(-((T % beat) / beat) * 4)
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
    top = sc.get("cap_y", 1050 if sc.get("emoji") else 900) - h / 2
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
    if sc.get("note") and t > 0.8:
        ImageDraw.Draw(ov).multiline_text((W / 2, 1420), sc["note"], font=font("bold", 30), anchor="mm", align="center",
                                          fill=(255, 255, 255, int(190 * clamp((t - 0.8) / 0.4))))
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


def s_fact(ov, sc, t, d, C, ev):
    """Fakten-Karte: Zähler, Emoji, Schlagzeile, Erklärung (erscheint, wenn sie gesprochen wird)."""
    dr = ImageDraw.Draw(ov)
    if sc.get("_label"):
        pill(dr, W / 2, SAFE_TOP + 40, sc["_label"], 46, C["accent"] + (255,), C["accent_text"] + (255,))
    bouncing_emoji(ov, sc.get("emoji"), 260, W / 2, 560, t)
    words = parse(sc["text"])
    size, placed, h = fit(words, sc.get("size", 108), C, 430, 4)
    top = 900 - h / 2
    draw_words(ov, placed, top, t, 0.1, min(0.12, 1.2 / max(1, len(placed))))
    if sc.get("sub"):
        st = sc.get("_sub_t", 0.3 + len(placed) * 0.12)
        _, sp, sh = fit(parse(sc["sub"]), 60, C, 300, 4)
        y = max(top + h + 40, 1120)
        k = (t - st) / 0.25
        if k > 0:
            dr.rounded_rectangle([MX - 20, y - 24, W - MX + 20, y + sh + 24], radius=36,
                                 fill=(0, 0, 0, int(120 * clamp(k))))
        draw_words(ov, sp, y, t, st, 0.035)


FACT_TYPES = ("fact", "stat", "bars", "myth", "calc", "badge")


def de_num(v, dec=1):
    return f"{v:.{dec}f}".replace(".", ",")


def fact_frame(ov, sc, t, C):
    """Gemeinsamer Rahmen der Daten-Szenen: Zähler oben, Schlagzeile, Erklärung unten."""
    dr = ImageDraw.Draw(ov)
    if sc.get("_label"):
        pill(dr, W / 2, SAFE_TOP + 40, sc["_label"], 46, C["accent"] + (255,), C["accent_text"] + (255,))
    _, placed, _ = fit(parse(sc["text"]), sc.get("size", 92), C, 270, 3)
    draw_words(ov, placed, 420, t, 0.08, min(0.1, 1.0 / max(1, len(placed))))
    if sc.get("sub"):
        st = sc.get("_sub_t", 1.5)
        _, sp, sh = fit(parse(sc["sub"]), 54, C, 170, 3)
        y = 1460 - sh - 10
        k = (t - st) / 0.25
        if k > 0:
            dr.rounded_rectangle([MX - 20, y - 22, W - MX + 20, y + sh + 18], radius=34,
                                 fill=(0, 0, 0, int(140 * clamp(k))))
        draw_words(ov, sp, y, t, st, 0.03)


def text_c(dr, x, y, txt, size, fill, anchor="mm", stroke=0):
    dr.text((x, y), txt, font=font("black", size), fill=fill, anchor=anchor,
            stroke_width=stroke, stroke_fill=(0, 0, 0, 255))


def s_stat(ov, sc, t, d, C, ev):
    """Großer Zähler + Personen-Reihe + Vergleichsbalken."""
    fact_frame(ov, sc, t, C)
    dr = ImageDraw.Draw(ov)
    v = sc["value"]
    k = ease_out((t - 0.3) / 1.2)
    if k > 0:
        text_c(dr, W / 2, 780, de_num(v * k, sc.get("decimals", 1)) + " " + sc.get("unit", "%"), 190,
               C["accent"] + (255,), stroke=10)
    n, hi = sc.get("people", 5), sc.get("highlight", [2])
    gap = (W - 2 * MX) / n
    for i in range(n):
        st = 0.6 + i * 0.12
        kk = (t - st) / 0.3
        if kk <= 0:
            continue
        cx, cy = MX + gap * (i + 0.5), 1000
        if i in hi:
            r = 88 * (1 + 0.05 * math.sin(t * 6))
            dr.ellipse([cx - r, cy - r, cx + r, cy + r], fill=C["accent"] + (int(230 * clamp(kk)),))
            paste_scaled(ov, emoji_img(sc.get("hi_emoji", "🧑"), 120), cx, cy, ease_back(kk), clamp(kk * 2))
        else:
            paste_scaled(ov, emoji_img(sc.get("emoji", "🧑"), 110), cx, cy, ease_back(kk), clamp(kk * 2) * 0.45)
    comp = sc.get("compare", [])
    vmax = max([c["value"] for c in comp] + [1])
    for j, c in enumerate(comp):
        y = 1140 + j * 72
        kk = ease_out((t - 1.3 - j * 0.2) / 0.8)
        if kk <= 0:
            continue
        f = font("bold", 38)
        dr.text((MX, y), c["label"], font=f, fill=(255, 255, 255, 230), anchor="lm")
        x0, x1 = MX + 250, W - MX - 150
        dr.rounded_rectangle([x0, y - 20, x0 + 40 + (x1 - x0 - 40) * c["value"] / vmax * kk, y + 20], radius=20,
                             fill=(C["accent"] if j == 0 else (255, 255, 255)) + (255,))
        dr.text((x0 + 60 + (x1 - x0 - 40) * c["value"] / vmax * kk, y), de_num(c["value"] * kk) + " %",
                font=font("black", 40), fill=(255, 255, 255, 255), anchor="lm")


def s_bars(ov, sc, t, d, C, ev):
    """Vergleichs-Balkendiagramm mit wachsenden Balken und hochzählenden Werten."""
    fact_frame(ov, sc, t, C)
    dr = ImageDraw.Draw(ov)
    bars = sc["bars"]
    vmax = max(b["value"] for b in bars)
    for i, b in enumerate(bars):
        y = 720 + i * 170
        k = ease_out((t - 0.5 - i * 0.35) / 1.0)
        if k <= 0:
            continue
        paste_scaled(ov, emoji_img(b.get("emoji", "📊"), 96), MX + 48, y + 30, ease_back(k * 1.5), clamp(k * 3))
        x0 = MX + 120
        dr.text((x0, y - 22), b["label"], font=font("bold", 42), fill=(255, 255, 255, 235), anchor="lm")
        maxw = W - MX - 170 - x0
        col = rgb(b["color"]) if b.get("color") else C["accent"]
        dr.rounded_rectangle([x0, y + 8, x0 + max(30, maxw * b["value"] / vmax * k), y + 64], radius=28,
                             fill=col + (255,))
        dr.text((x0 + max(30, maxw * b["value"] / vmax * k) + 18, y + 36), de_num(b["value"] * k, b.get("decimals", 1)),
                font=font("black", 50), fill=(255, 255, 255, 255), anchor="lm")
    if sc.get("note"):
        a = int(210 * clamp((t - 1.8) / 0.4))
        if a:
            dr.text((W / 2, 720 + len(bars) * 170 - 20), sc["note"], font=font("bold", 34),
                    fill=(255, 255, 255, a), anchor="mm")


def s_myth(ov, sc, t, d, C, ev):
    """Mythos: Dampfwolke, darum erscheinen Stoffe, die enthalten sein können."""
    fact_frame(ov, sc, t, C)
    dr = ImageDraw.Draw(ov)
    paste_scaled(ov, emoji_img(sc.get("emoji", "💨"), 300), W / 2 + math.sin(t * 1.5) * 25, 860,
                 ease_back(t / 0.4), clamp(t * 3))
    spots = [(-260, 700), (250, 740), (-250, 1030), (240, 1070), (0, 1150)]
    for i, chip in enumerate(sc.get("chips", [])):
        k = (t - 1.0 - i * 0.3) / 0.3
        if k <= 0:
            continue
        dx, cy = spots[i % len(spots)]
        cx = W / 2 + dx
        e = ease_back(k)
        f = font("black", int(42 * e) or 1)
        tw = f.getlength(chip)
        dr.rounded_rectangle([cx - tw / 2 - 26, cy - 34 * e, cx + tw / 2 + 26, cy + 34 * e], radius=34,
                             fill=(239, 68, 68, 235), outline=(0, 0, 0, 255), width=4)
        dr.text((cx, cy), chip, font=f, fill=(255, 255, 255, 255), anchor="mm")


def s_calc(ov, sc, t, d, C, ev):
    """Rechnung Schritt für Schritt + fallende Münzen."""
    fact_frame(ov, sc, t, C)
    toks = sc["steps"]
    ims = [word_img(x, 100, "box" if i == len(toks) - 1 else "normal", C) for i, x in enumerate(toks)]
    gap = 26
    rows = [list(range(len(toks)))]
    if sum(i.width for i in ims) + gap * (len(ims) - 1) > W - 2 * MX:  # zu breit: Ergebnis in eigene Zeile
        cut = max(i for i, x in enumerate(toks) if x in ("=", "≈")) if any(x in ("=", "≈") for x in toks) else len(toks) // 2
        rows = [list(range(cut)), list(range(cut, len(toks)))]
    for r, row in enumerate(rows):
        total = sum(ims[i].width for i in row) + gap * (len(row) - 1)
        scale = min(1.0, (W - 2 * MX) / total)
        x = (W - total * scale) / 2
        y = 780 + r * 150 - (len(rows) - 1) * 40
        for i in row:
            s_, a = stamp(t, 0.4 + i * 0.3)
            paste_scaled(ov, ims[i], x + ims[i].width * scale / 2, y, s_ * scale, a)
            x += (ims[i].width + gap) * scale
    coin = emoji_img(sc.get("emoji", "🪙"), 110)
    n = sc.get("coins", 7)
    for i in range(n):
        st = 0.4 + len(toks) * 0.3 + i * 0.12
        k = (t - st) / 0.5
        if k <= 0:
            continue
        ex, ey = W / 2 + (i - (n - 1) / 2) * 80, 1150 - (i % 2) * 40
        y = 560 + (ey - 560) * ease_back(k)
        paste_scaled(ov, coin, ex, y, 1, clamp(k * 3), (i * 37) % 30 - 15)


def s_badge(ov, sc, t, d, C, ev):
    """Altersgrenze als Stempel + Rückgabe-Symbol."""
    fact_frame(ov, sc, t, C)
    dr = ImageDraw.Draw(ov)
    k = ease_back((t - 0.3) / 0.35)
    if k > 0:
        r = 170 * k * (1 + 0.03 * math.sin(t * 5))
        cx, cy = W / 2, 880
        dr.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(255, 255, 255, 240), outline=(239, 68, 68, 255),
                   width=int(28 * k) or 1)
        text_c(dr, cx, cy + 6, sc.get("badge", "18+"), int(135 * k) or 1, (20, 20, 20, 255))
    row = sc.get("row")
    if row:
        k2 = (t - 1.3) / 0.35
        if k2 > 0:
            paste_scaled(ov, emoji_img(row[0], 120), W / 2 - 230, 1175, ease_back(k2), clamp(k2 * 2))
            ax = W / 2 - 120 + 240 * clamp((t - 1.5) / 0.4)
            if t > 1.5:
                dr.line([(W / 2 - 120, 1175), (ax, 1175)], fill=C["accent"] + (255,), width=14)
                if t > 1.9:
                    dr.polygon([(W / 2 + 140, 1175), (W / 2 + 105, 1145), (W / 2 + 105, 1205)],
                               fill=C["accent"] + (255,))
            k3 = (t - 1.9) / 0.35
            if k3 > 0:
                paste_scaled(ov, emoji_img(row[1], 130), W / 2 + 230, 1175, ease_back(k3), clamp(k3 * 2))


def ease_io(t):
    t = clamp(t)
    return t * t * (3 - 2 * t)


def draw_chat(ov, ch, t):
    """Handy-Nachricht mit Tipp-Animation."""
    if ch:
        at = ch.get("at", 0.3)
        if t > at:
            bx0, by0, bw = MX, ch.get("y", 470), W - 2 * MX
            f = font("bold", 50)
            fn = font("black", 36)
            k = ease_back((t - at) / 0.3)
            typing = t - at < ch.get("typing", 0.8)
            lines, cur = [], ""
            for w in ch["text"].split():
                if f.getlength(cur + " " + w) > bw - 80 and cur:
                    lines.append(cur); cur = w
                else:
                    cur = (cur + " " + w).strip()
            lines.append(cur)
            bh = 90 + (60 if typing else 62 * len(lines))
            ov_b = Image.new("RGBA", (bw, int(bh) + 10), (0, 0, 0, 0))
            db = ImageDraw.Draw(ov_b)
            db.rounded_rectangle([0, 0, bw - 1, bh], radius=40, fill=(255, 255, 255, 245))
            db.text((40, 22), ch.get("from", ""), font=fn, fill=(37, 99, 235, 255))
            if typing:
                for j in range(3):
                    r = 11 + 5 * max(0, math.sin(t * 9 - j))
                    db.ellipse([50 + j * 46 - r, 100 - r, 50 + j * 46 + r, 100 + r], fill=(120, 120, 120, 255))
            else:
                for j, ln in enumerate(lines):
                    db.text((40, 78 + j * 62), ln, font=f, fill=(15, 15, 15, 255))
            paste_scaled(ov, ov_b, bx0 + bw / 2, by0 + bh / 2, k, clamp(k * 2))


def s_story(ov, sc, t, d, C, ev):
    """Erzähl-Szene: bewegte Emoji-Figuren, Handy-Chat, Effekte und Untertitel."""
    dr = ImageDraw.Draw(ov)
    fx = sc.get("fx", {})
    if fx.get("rain"):
        rnd = random.Random(int(t * 30))
        for _ in range(70):
            x, y = rnd.uniform(0, W), rnd.uniform(0, H)
            dr.line([(x, y), (x - 8, y + 46)], fill=(180, 200, 255, 70), width=3)
    for a in sc.get("actors", []):
        at = a.get("at", 0.0)
        k = (t - at) / 0.35
        if k <= 0:
            continue
        mv_k = ease_io((t - at) / a.get("dur", max(0.1, d - at)))
        x0, y0 = a.get("x", 0.5), a.get("y", 0.45)
        x1, y1 = a.get("to", [x0, y0])
        x = (x0 + (x1 - x0) * mv_k) * W
        y = (y0 + (y1 - y0) * mv_k) * H
        y -= abs(math.sin(t * a.get("bob_speed", 7) + at)) * a.get("bob", 0) * 18
        size = a.get("s", 220)
        if a.get("pulse"):
            size *= 1 + 0.06 * math.sin(t * 6)
        im = emoji_img(a["e"], int(size))
        if a.get("flip"):
            im = im.transpose(Image.FLIP_LEFT_RIGHT)
        sc_k = ease_back(k) if a.get("pop", True) else 1
        ang = math.sin(t * a.get("bob_speed", 7)) * a.get("sway", 0) * 8
        paste_scaled(ov, im, x, y, sc_k, clamp(k * 2) * a.get("alpha", 1.0), ang)
    draw_chat(ov, sc.get("chat"), t)
    cap = dict(sc)
    cap["emoji"] = None
    cap["cap_y"] = sc.get("cap_y", 1300)
    cap.setdefault("size", 86)
    s_captions(ov, cap, t, d, C, ev)


def s_cartoon(ov, sc, t, d, C, ev):
    """Cartoon-Dialog: gezeichneter Hintergrund, Figuren mit Lippenbewegung, Untertitel."""
    import cartoon as ct
    ov.alpha_composite(ct.background(sc.get("bg", "black")))
    cast = sc["_cast"]
    lines = sc.get("_lines", [])
    cur = next((ln for ln in lines if ln["start"] <= t < ln["start"] + ln["dur"]), None)
    shown = sc.get("show", [])
    xs = {c["who"]: c.get("x", 0.5) for c in shown}
    for i, c in enumerate(shown):
        who = c["who"]
        at = c.get("at", 0.0)
        if t < at:
            continue
        k = ease_out((t - at) / c.get("enter", 0.6)) if "from" in c else 1.0
        x = (c.get("from", c.get("x", 0.5)) + (c.get("x", 0.5) - c.get("from", c.get("x", 0.5))) * k) * W
        if "to" in c:
            x = (c.get("x", 0.5) + (c["to"] - c.get("x", 0.5)) * ease_io((t - at) / max(0.1, d - at))) * W
        talking = cur is not None and cur["who"] == who
        mouth = 0.0
        expr, pose = c.get("expr", "neutral"), c.get("pose", "idle")
        if talking:
            idx = int((t - cur["start"]) * FPS)
            env = cur["env"]
            mouth = env[idx] if 0 <= idx < len(env) else 0.0
            expr, pose = cur.get("expr", expr), cur.get("pose", pose)
        else:
            past = [ln for ln in lines if ln["who"] == who and ln["start"] <= t]
            if past:
                expr = past[-1].get("expr_after", expr)
        look_dir = c.get("look", 0.0)
        if cur and cur["who"] != who and cur["who"] in xs:
            look_dir = 0.8 if xs[cur["who"]] > c.get("x", 0.5) else -0.8
        elif talking and len(shown) > 1:
            other = [o for o in shown if o["who"] != who]
            look_dir = 0.7 if other[0].get("x", 0.5) > c.get("x", 0.5) else -0.7
        if pose == "run" and k < 1:
            pass
        look = dict(cast.get(who, {}).get("look", {}))
        ct.draw_character(ov, look, x, c.get("ground", 1720), c.get("scale", 1.0) * cast.get(who, {}).get("size", 1.0),
                          t, mouth=mouth, expr=expr, pose=pose, look_dir=look_dir, talking=talking and mouth > 0.05,
                          seed=i * 3 + len(who))
    if sc.get("bg") == "car_night":
        ct.car_foreground(ov)
    for pr in sc.get("props", []):  # Gegenstände (Emoji) im Bild, z. B. Blumen, Handy, Umschlag
        k = (t - pr.get("at", 0.0)) / 0.3
        if k > 0:
            paste_scaled(ov, emoji_img(pr["e"], pr.get("s", 160)), pr.get("x", 0.5) * W, pr.get("y", 0.6) * H,
                         ease_back(k), clamp(k * 2), math.sin(t * 2) * pr.get("wobble", 0) * 6)
    draw_chat(ov, sc.get("chat"), t)
    if cur and sc.get("_subtitles", True) and cur.get("text"):
        name = cast.get(cur["who"], {}).get("name", cur["who"].capitalize())
        dr = ImageDraw.Draw(ov)
        f = font("black", 50)
        fn = font("black", 38)
        words, rows, row = cur["text"].replace("*", "").split(), [], ""
        for w_ in words:
            if f.getlength(row + " " + w_) > W - 2 * MX - 60 and row:
                rows.append(row); row = w_
            else:
                row = (row + " " + w_).strip()
        rows.append(row)
        rows = rows[-3:]
        bh = 70 + 62 * len(rows)
        y0 = 1530 - bh
        dr.rounded_rectangle([MX - 20, y0, W - MX + 20, y0 + bh], radius=30, fill=(0, 0, 0, 175))
        col = rgb(cast.get(cur["who"], {}).get("color", "#facc15"))
        dr.text((MX + 10, y0 + 14), name.upper(), font=fn, fill=col + (255,))
        for j, r_ in enumerate(rows):
            dr.text((MX + 10, y0 + 60 + j * 62), r_, font=f, fill=(255, 255, 255, 255))


def s_motion(ov, sc, t, d, C, ev):
    """Dunkle Motion-Grafik im Motivations-Stil (siehe motion.py)."""
    import motion
    ov.alpha_composite(motion.render_scene(sc, t, d))


def story_overlay(img, sc, t, fxcache, grain=True):
    """Kino-Effekte über dem fertigen Bild: Sirenenlicht, Farbstich, Blitz, Vignette, Filmkorn."""
    fx = sc.get("fx", {})
    if fx.get("siren"):
        a = int(28 + 22 * math.sin(t * 9))
        col = (255, 0, 40) if int(t * 2.2) % 2 == 0 else (30, 60, 255)
        img.alpha_composite(Image.new("RGBA", (W, H), col + (max(0, a),)))
    if fx.get("tint"):
        img.alpha_composite(Image.new("RGBA", (W, H), rgb(fx["tint"]) + (int(fx.get("tint_alpha", 50)),)))
    if fx.get("flash") and t < 0.25:
        col = (255, 0, 0) if fx["flash"] == "red" else (255, 255, 255)
        img.alpha_composite(Image.new("RGBA", (W, H), col + (int(170 * (1 - t / 0.25)),)))
    if fx.get("dark"):
        img.alpha_composite(Image.new("RGBA", (W, H), (0, 0, 0, int(fx["dark"] * 255))))
    if not grain:
        return
    if "vig" not in fxcache:
        yy, xx = np.mgrid[0:H // 4, 0:W // 4]
        r = np.sqrt(((xx - W / 8) / (W / 8)) ** 2 + ((yy - H / 8) / (H / 8)) ** 2)
        a = (np.clip(r - 0.55, 0, 1) / 0.6) ** 1.6 * 230
        v = np.zeros((H // 4, W // 4, 4), np.uint8)
        v[..., 3] = np.clip(a, 0, 230).astype(np.uint8)
        fxcache["vig"] = Image.fromarray(v, "RGBA").resize((W, H), Image.BILINEAR)
        rng = np.random.default_rng(3)
        fxcache["grain"] = []
        for _ in range(4):
            g = rng.integers(0, 255, (H // 3, W // 3), dtype=np.uint8)
            ga = np.dstack([g, g, g, np.full_like(g, 16)])
            fxcache["grain"].append(Image.fromarray(ga, "RGBA").resize((W, H), Image.NEAREST))
    img.alpha_composite(fxcache["vig"])
    img.alpha_composite(fxcache["grain"][int(t * 24) % 4])


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


SCENES = {"hook": s_hook, "punch": s_punch, "captions": s_captions, "quiz": s_quiz, "cta": s_cta, "scan": s_scan, "fact": s_fact,
          "stat": s_stat, "bars": s_bars, "myth": s_myth, "calc": s_calc, "badge": s_badge,
          "story": s_story, "cartoon": s_cartoon, "motion": s_motion}


# ---------- Sprachausgabe (Piper, offline) ----------

PRONOUNCE = {"SmartWasteAI": "Smart Wehst A I", "1 %": "ein Prozent", "Cent": "Sent", "Tetra Pak": "Tetrapack", "Kassenbon": "Kassenbong", "Quiz": "Kwiss", "MP3": "Em-Pe-Drei", "Red Flags": "Rädd Fläggs", "Red Flag": "Rädd Fläck",
             "Score": "Skohr", "Kommis": "Kommis"}


_ONES = ["null", "eins", "zwei", "drei", "vier", "fünf", "sechs", "sieben", "acht", "neun", "zehn", "elf", "zwölf",
         "dreizehn", "vierzehn", "fünfzehn", "sechzehn", "siebzehn", "achtzehn", "neunzehn"]
_TENS = {2: "zwanzig", 3: "dreißig", 4: "vierzig", 5: "fünfzig", 6: "sechzig", 7: "siebzig", 8: "achtzig", 9: "neunzig"}


def zahl(n):
    """Ganze Zahl als deutsches Wort (bis 999 999)."""
    if n < 20:
        return _ONES[n]
    if n < 100:
        t, o = divmod(n, 10)
        return _TENS[t] if o == 0 else ("ein" if o == 1 else _ONES[o]) + "und" + _TENS[t]
    if n < 1000:
        h, r = divmod(n, 100)
        return ("ein" if h == 1 else _ONES[h]) + "hundert" + (zahl(r) if r else "")
    if n < 1000000:
        t, r = divmod(n, 1000)
        return ("ein" if t == 1 else zahl(t)) + "tausend" + (zahl(r) if r else "")
    return str(n)


def jahr(n):
    """Jahreszahlen 1100-1999 wie gesprochen: 1880 -> achtzehnhundertachtzig."""
    h, r = divmod(n, 100)
    return zahl(h) + "hundert" + (zahl(r) if r else "")


def german_numbers(s):
    """Zahlen als deutsche Wörter ausschreiben (2024 -> zweitausendvierundzwanzig, 1922 -> neunzehnhundertzweiundzwanzig)."""
    def word(m):
        n = int(m.group(0))
        return jahr(n) if len(m.group(0)) == 4 and 1100 <= n <= 1999 else zahl(n)
    return re.sub(r"\d+", word, s)


LEAD = 0.12  # Sprechbeginn nach dem Schnitt


def speech_text(text, extra=None):
    s = "".join(ch for ch in text.replace("*", "") if not is_emoji(ch))
    for a, b in {**PRONOUNCE, **(extra or {})}.items():
        s = s.replace(a, b)
    s = re.sub(r"(\d+)\s*/\s*(\d+)", r"\1 von \2", s)
    # Anglizismus "recyceln" deutsch korrekt: ri-SAI-keln
    s = re.sub(r"[Rr]ecyc", lambda m: "Rissaik" if m.group(0)[0] == "R" else "rissaik", s)
    s = re.sub(r"(\d)\.(\d{3})(?!\d)", r"\1\2", s)  # Tausenderpunkt: 100.000 -> 100000
    s = re.sub(r"(\d)\.(\d{3})(?!\d)", r"\1\2", s)
    s = re.sub(r"(\d+),(\d+)", r"\1 Komma \2", s)
    s = re.sub(r"(\d+)\s*[–-]\s*(\d+)", r"\1 bis \2", s)
    s = s.replace("%", " Prozent").replace("€", " Euro")
    s = german_numbers(s)
    s = s.replace("&", " und ").replace("+", " plus ").replace("=", " ist ").replace("·", ",").replace("…", "...")
    s = re.sub(r"\s+", " ", s).strip()
    return s if not s or s[-1] in ".!?:," else s + "."


class Voice:
    def __init__(self, path, speed=0.92, speaker=None):
        from piper import PiperVoice, SynthesisConfig
        self.v = PiperVoice.load(path)
        sid = None
        if speaker is not None:
            sid = self.v.config.speaker_id_map.get(speaker, speaker) if isinstance(speaker, str) else speaker
        self.sr = self.v.config.sample_rate
        orig = self.v.phonemize
        needs_fix = "\u0327" not in self.v.config.phoneme_id_map

        def fixed(text):
            if not needs_fix:
                return orig(text)  # neuere espeak-Versionen zerlegen "ç" (ich-Laut) in c + Cedille
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
        self.cfg = SynthesisConfig(speaker_id=sid, length_scale=speed, noise_scale=0.45, noise_w_scale=0.6)

    def say(self, text):
        gap = np.zeros(int(self.sr * 0.07), np.float32)
        parts = []
        for c in self.v.synthesize(text, syn_config=self.cfg):
            parts += [c.audio_float_array, gap]
        a = np.concatenate(parts) if parts else np.zeros(1, np.float32)
        loud = np.where(np.abs(a) > 0.01)[0]
        return a[max(0, loud[0] - int(self.sr * 0.08)):loud[-1] + int(self.sr * 0.3)] if len(loud) else a


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
        elif tp in FACT_TYPES:
            a1 = say(sc.get("say", sc["text"]))
            a2 = say(sc.get("say_sub", sc.get("sub", ""))) if sc.get("sub") or sc.get("say_sub") else np.zeros(1, np.float32)
            gap = np.zeros(int(voice.sr * 0.18), np.float32)
            a = np.concatenate([a1, gap, a2])
            sc["_sub_t"] = LEAD + L(a1) + 0.1
            sc["duration"] = max(sc.get("duration", 2.0), LEAD + L(a) + 0.35)
            clips.append((T0 + LEAD, a))
        else:
            text = sc.get("say") or (sc["text"] + (" " + sc["sub"] if sc.get("sub") else ""))
            if tp == "hook" and sc.get("sub") and not sc.get("say"):
                text = sc["text"].rstrip() + ("" if sc["text"].rstrip()[-1:] in ".!?" else ".") + " " + sc["sub"]
            a = say(text)
            tail = sc.get("tail", {"captions": 0.25, "punch": 0.2, "hook": 0.35, "cta": 0.9, "story": 0.5}.get(tp, 0.3))
            vis = sc.get("duration", {"hook": 1.6, "punch": 1.0, "cta": 2.6}.get(tp, 1.0))
            sc["duration"] = max(vis, LEAD + L(a) + tail)
            clips.append((T0 + LEAD, a))
            if tp in ("captions", "story"):  # Karaoke-Timing grob an die Sprache koppeln
                words = [w for w, _ in parse(sc["text"]) if w != "\n"]
                wts = [len(w) + 2 + (4 if w.endswith((".", "!", "?", ",", ":")) else 0) for w in words]
                tot, acc, starts = sum(wts), 0, []
                for wgt in wts:
                    starts.append(LEAD + L(a) * acc / tot)
                    acc += wgt
                sc["_wt"] = starts
        T0 += dur_of(sc)
    return clips


class CoquiVoice:
    """Coqui-VITS-Stimme über sherpa-onnx (z. B. css10: klare deutsche Frauenstimme)."""
    def __init__(self, path, speed=1.0):
        import sherpa_onnx
        cfg = sherpa_onnx.OfflineTtsConfig(model=sherpa_onnx.OfflineTtsModelConfig(
            vits=sherpa_onnx.OfflineTtsVitsModelConfig(model=os.path.join(path, "model.onnx"),
                                                       tokens=os.path.join(path, "tokens.txt")), num_threads=4))
        self.tts = sherpa_onnx.OfflineTts(cfg)
        self.sr = self.tts.sample_rate
        self.speed = speed

    def say(self, text, speed=None):
        g = self.tts.generate(text, sid=0, speed=1.0 / (speed or self.speed))
        a = np.array(g.samples, np.float32)
        loud = np.where(np.abs(a) > 0.01)[0]
        return a[max(0, loud[0] - int(self.sr * 0.08)):loud[-1] + int(self.sr * 0.3)] if len(loud) else a


CLEAN = {"on": True}  # saubere Stimme: keine Tonhöhen-Tricks, kein Zittern, keine Sättigung

# Emotionen: Tempo (length_scale, >1 = langsamer), Tonhöhe (Halbtöne), Lautstärke, Zittern, Thorsten-Variante
EMOTIONS = {
    "neutral": dict(speed=1.0, pitch=0.0, gain=1.0),
    "angry": dict(speed=0.9, pitch=1.0, gain=1.25, spk="angry"),
    "shout": dict(speed=0.87, pitch=2.0, gain=1.45, spk="angry"),
    "sad": dict(speed=1.17, pitch=-1.0, gain=0.85, vibrato=0.12),
    "cry": dict(speed=1.22, pitch=-0.5, gain=0.9, vibrato=0.35),
    "shock": dict(speed=0.95, pitch=2.0, gain=1.15, spk="surprised"),
    "happy": dict(speed=0.94, pitch=1.5, gain=1.1, spk="amused"),
    "whisper": dict(speed=1.1, pitch=0.0, gain=0.7, spk="whisper"),
    "cold": dict(speed=1.12, pitch=-1.5, gain=0.95),
    "nervous": dict(speed=0.88, pitch=1.0, gain=1.0, vibrato=0.15),
}


def resolve_voice(name):
    """'thorsten-high' / 'thorsten_emotional:whisper' / 'kerstin' -> (Pfad, Sprecher)."""
    speaker = None
    if ":" in name:
        name, speaker = name.split(":", 1)
    if name.endswith(".onnx"):
        return name, speaker
    if name == "css10":
        return os.path.join(HERE, "voices", "vits-coqui-de-css10"), "coqui"
    for cand in (f"de_DE-{name}-high.onnx", f"de_DE-{name}-medium.onnx", f"de_DE-{name}.onnx",
                 f"de-{name}-low.onnx", f"de-{name}.onnx"):
        p = os.path.join(HERE, "voices", cand)
        if os.path.exists(p):
            return p, speaker
    raise FileNotFoundError(f"Stimme nicht gefunden: {name}")


def to_sr(a, sr, pitch=0.0, vibrato=0.0):
    """Sprachclip auf 44,1 kHz bringen, optional Tonhöhe (Halbtöne) und Zittern (Weinen) ändern."""
    af = "aresample=%d:resampler=soxr" % SR
    if pitch:
        af = "rubberband=pitch=%.4f:formant=preserved:pitchq=quality," % (2 ** (pitch / 12)) + af
    raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-f", "f32le", "-ar", str(sr), "-ac", "1", "-i", "-",
                          "-af", af, "-f", "f32le", "-ac", "1", "-"], input=a.astype(np.float32).tobytes(),
                         capture_output=True).stdout
    out = np.nan_to_num(np.frombuffer(raw, np.float32).astype(float), nan=0.0, posinf=0.0, neginf=0.0)
    if vibrato:  # zitternde Stimme (Weinen): Tonhöhe schwankt mit 5,5 Hz um ±(2·vibrato) Halbtöne
        f = 5.5
        amp = (2 ** (2 * vibrato / 12) - 1) / (2 * math.pi * f) * SR
        n = np.arange(len(out))
        idx = np.clip(n - amp * (1 + np.sin(2 * math.pi * f * n / SR)), 0, len(out) - 1)
        out = np.interp(idx, n, out)
    return out


def lip_env(a):
    """Lautstärke pro Videobild (0..1) für die Mundbewegung."""
    n = SR // FPS
    fr = [np.sqrt(np.mean(a[i:i + n] ** 2)) for i in range(0, len(a), n)]
    fr = np.array(fr) if fr else np.zeros(1)
    ref = np.percentile(fr, 90) or 1
    env = np.clip(fr / ref, 0, 1)
    env = np.where(env < 0.15, 0, env)
    return np.convolve(env, [0.25, 0.5, 0.25], "same")


def plan_cast(scenes, cast, extra, speed):
    """Mehrere Stimmen: jede Figur spricht mit eigener Stimme. Liefert Clips bei 44,1 kHz."""
    voices = {}

    def get(spec):
        if spec not in voices:
            path, spk = resolve_voice(spec)
            voices[spec] = CoquiVoice(path, speed) if spk == "coqui" else Voice(path, speed, spk)
        return voices[spec]

    def speak(m, ln):
        """Eine Zeile mit Emotion + Wortbetonung (*Wort*) sprechen -> Audio bei 44,1 kHz."""
        emo = EMOTIONS.get(ln.get("emo", "neutral"), EMOTIONS["neutral"])
        spec = m["voice"]
        if spec.startswith("thorsten_emotional"):
            spec = "thorsten_emotional:" + (ln.get("style") or emo.get("spk") or "neutral")
        elif ln.get("style"):
            spec = spec.split(":")[0] + ":" + ln["style"]
        v = get(spec)
        base_pitch = m.get("pitch", 0) + (0 if CLEAN["on"] else emo["pitch"]) + ln.get("pitch", 0)
        sp = m.get("speed", 1.0) * emo["speed"]
        text = ln.get("say", ln["text"])
        plain = text.replace("*", "")
        spans, pos = [], 0  # Lage der *betonten* Wörter im Satz (als Anteil 0..1)
        for part in re.split(r"(\*[^*]+\*)", text):
            n = len(part.replace("*", ""))
            if part.startswith("*") and plain:
                spans.append((pos / len(plain), (pos + n) / len(plain)))
            pos += n
        st = speech_text(plain, extra)
        if isinstance(v, CoquiVoice):
            raw = v.say(st, sp)
        else:
            old = v.cfg.length_scale
            v.cfg.length_scale = sp
            raw = v.say(st)
            v.cfg.length_scale = old
        a = to_sr(raw, v.sr, base_pitch, 0 if CLEAN["on"] else emo.get("vibrato", 0))
        boost = 1.25 if CLEAN["on"] else 1.35
        if spans:  # betonte Wörter lauter (weiche Rampen)
            env = np.ones(len(a))
            loud = np.where(np.abs(a) > 0.02)[0]
            s0, s1 = (loud[0], loud[-1]) if len(loud) else (0, len(a))
            for f0, f1 in spans:
                i0, i1 = int(s0 + (s1 - s0) * f0), int(s0 + (s1 - s0) * f1)
                ramp = int(SR * 0.04)
                env[i0:i1] = np.maximum(env[i0:i1], boost)
                env[max(0, i0 - ramp):i0] = np.maximum(env[max(0, i0 - ramp):i0], np.linspace(1, boost, i0 - max(0, i0 - ramp)))
                env[i1:i1 + ramp] = np.maximum(env[i1:i1 + ramp], np.linspace(boost, 1, len(env[i1:i1 + ramp])))
            a = a * env
        out = [a]
        a = np.concatenate(out) if out else np.zeros(1)
        return a * emo["gain"] * m.get("gain", 1.0)

    narr = cast.get("erzähler", {"voice": "thorsten-high"})
    clips, T0 = [], 0.0
    for sc in scenes:
        tp = sc.get("type")
        sc["_cast"] = cast
        if tp == "cartoon":
            t, lines = LEAD + sc.get("lead", 0.0), []
            for ln in sc.get("lines", []):
                m = cast.get(ln["who"], narr)
                if ln.get("text") and m.get("voice"):
                    a = speak(m, ln)
                    clips.append((T0 + t, a))
                    dur = len(a) / SR
                    env = lip_env(a)
                else:
                    dur = ln.get("dur", 1.0)
                    env = np.full(int(dur * FPS), 0.6)
                for name, off in ln.get("sfx", []):
                    sc.setdefault("sfx", []).append([name, t + off])
                lines.append(dict(ln, start=t, dur=dur, env=env))
                t += dur + ln.get("pause", 0.22)
            sc["_lines"] = lines
            sc["duration"] = max(sc.get("duration", 0), t + sc.get("tail", 0.35))
        elif tp in FACT_TYPES:
            a1 = speak(narr, {"text": sc.get("say", sc["text"]), "emo": sc.get("emo", "neutral")})
            a = a1
            if sc.get("sub") or sc.get("say_sub"):
                a2 = speak(narr, {"text": sc.get("say_sub", sc.get("sub", "")), "emo": sc.get("emo_sub", "neutral")})
                a = np.concatenate([a1, np.zeros(int(SR * 0.25)), a2])
            sc["_sub_t"] = LEAD + len(a1) / SR + 0.12
            clips.append((T0 + LEAD, a))
            sc["duration"] = max(sc.get("duration", 2.0), LEAD + len(a) / SR + sc.get("tail", 0.45))
        else:
            text = sc.get("say") or (sc.get("text", "") + (" " + sc["sub"] if sc.get("sub") else ""))
            if text.strip():
                a = speak(narr, {"text": text, "emo": sc.get("emo", "neutral")})
                lead = 0.04 if tp == "motion" else LEAD
                clips.append((T0 + lead, a))
                sc["_say_dur"] = len(a) / SR
                if tp == "motion":
                    sc["duration"] = max(sc.get("duration", 0.6), lead + len(a) / SR + sc.get("tail", 0.18))
                    T0 += dur_of(sc)
                    continue
                tail = {"captions": 0.25, "punch": 0.2, "hook": 0.35, "cta": 0.9, "motion": 0.35}.get(tp, 0.6)
                sc["duration"] = max(sc.get("duration", 1.0), LEAD + len(a) / SR + sc.get("tail", tail))
        T0 += dur_of(sc)
    return clips


def voice_bus_sr(clips, total):
    bus = np.zeros(int((total + 1) * SR), np.float32)
    for at, a in clips:
        i = int(at * SR)
        j = min(len(bus), i + len(a))
        bus[i:j] += a[:j - i]
    pcm = (np.clip(bus / (np.max(np.abs(bus)) or 1) * 0.9, -1, 1) * 32767).astype(np.int16).tobytes()
    if CLEAN["on"]:  # sanft: kein Höhen-Boost, Zischlaute gezähmt, leichte Kompression
        af = ("highpass=f=80,equalizer=f=250:t=q:w=1:g=-2,equalizer=f=2500:t=q:w=1.5:g=1.5,"
              "lowpass=f=9500,acompressor=threshold=-20dB:ratio=2:attack=10:release=150:makeup=1.5")
    else:
        af = ("highpass=f=85,equalizer=f=280:t=q:w=1:g=-3,equalizer=f=3000:t=q:w=1.2:g=3.5,"
              "equalizer=f=7000:t=q:w=1:g=2,acompressor=threshold=-18dB:ratio=2:attack=5:release=80:makeup=2")
    raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-f", "s16le", "-ar", str(SR), "-ac", "1", "-i", "-",
                          "-af", af, "-f", "f32le", "-ac", "1", "-"], input=pcm, capture_output=True).stdout
    return np.frombuffer(raw, np.float32).astype(float)


def voice_bus(clips, sr, total, pitch=0.0):
    """Legt die Sprachclips auf eine Spur und veredelt sie (EQ, Kompressor) auf 44,1 kHz."""
    bus = np.zeros(int((total + 1) * sr), np.float32)
    for at, a in clips:
        i = int(at * sr)
        j = min(len(bus), i + len(a))
        bus[i:j] += a[:j - i]
    pcm = (np.clip(bus / (np.max(np.abs(bus)) or 1) * 0.9, -1, 1) * 32767).astype(np.int16).tobytes()
    af = ("highpass=f=85,equalizer=f=280:t=q:w=1:g=-3,equalizer=f=3000:t=q:w=1.2:g=3.5,"
          "equalizer=f=7000:t=q:w=1:g=2,acompressor=threshold=-20dB:ratio=3:attack=5:release=60:makeup=2,"
          "aresample=%d" % SR)
    if pitch:
        af = "rubberband=pitch=%.4f:formant=preserved," % (2 ** (pitch / 12)) + af
    raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-f", "s16le", "-ar", str(sr), "-ac", "1", "-i", "-",
                          "-af", af, "-f", "f32le", "-ac", "1", "-"], input=pcm, capture_output=True).stdout
    return np.frombuffer(raw, np.float32).astype(float)


# ---------- Audio ----------

def synth_audio(total, events, bpm, beat_on, music=None, music_volume=0.6, voice=None, style="beat"):
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
    elif beat_on and style == "drama":
        # Düstere Spannungsmusik: Drone, Moll-Flächen, Herzschlag
        beat = 60 / bpm
        x = np.arange(n) / SR
        trem = 1 + 0.35 * np.sin(2 * np.pi * 0.2 * x)
        mix += (np.sin(2 * np.pi * 55 * x) * 0.5 + np.sin(2 * np.pi * 82.41 * x) * 0.25) * trem * 0.6
        chords = [[220, 261.6, 329.6], [174.6, 220, 261.6], [146.8, 174.6, 220], [164.8, 207.7, 246.9]]
        bar_len = beat * 4
        b = 0
        while b * bar_len < total:
            xx = tt(bar_len)
            pad = sum(np.sin(2 * np.pi * f * xx) + 0.2 * np.sin(6 * np.pi * f * xx) for f in chords[b % 4]) / 3
            pad *= np.minimum(1, xx / 1.2) * np.minimum(1, (bar_len - xx) / 0.8)
            add(pad, b * bar_len, 0.22)
            b += 1
        k = 0
        while k * beat < total:
            add(kick(), k * beat, 0.5)
            add(kick(), k * beat + 0.2, 0.3)
            k += 1
    elif beat_on and style == "ambient":
        # Ruhige Ambient-Musik: weiches Klavier-Arpeggio, warme Fläche, Hall – kein Beat, keine Höhen
        beat = 60 / bpm
        chords = [[261.63, 329.63, 392.0, 493.88], [220.0, 261.63, 329.63, 392.0],
                  [174.61, 220.0, 261.63, 329.63], [196.0, 246.94, 293.66, 392.0]]  # Cmaj7 Am7 Fmaj7 G
        bar_len = beat * 4

        def piano(f, d=2.2):
            x = tt(d)
            s_ = np.sin(2 * np.pi * f * x) + 0.35 * np.sin(4 * np.pi * f * x) + 0.12 * np.sin(6 * np.pi * f * x)
            return s_ * np.exp(-x * 2.2) * np.minimum(1, x * 120)

        b = 0
        while b * bar_len < total + 1:
            ch = chords[b % 4]
            at = b * bar_len
            xx = tt(bar_len + 0.5)
            pad = sum(np.sin(2 * np.pi * f / 2 * xx) for f in ch[:3]) / 3
            pad *= np.minimum(1, xx / 1.5) * np.minimum(1, np.maximum(0, (bar_len + 0.5 - xx)) / 1.0)
            add(pad, at, 0.22)
            for k, ni in enumerate([0, 1, 2, 3, 2, 1, 2, 3]):
                add(piano(ch[ni]), at + k * beat / 2, 0.16 if k % 4 == 0 else 0.11)
            b += 1
        # einfacher Hall (zwei Echos, gedämpft) für Raumgefühl
        d1, d2 = int(SR * 0.21), int(SR * 0.37)
        wet = np.zeros(n)
        wet[d1:] += mix[:-d1] * 0.35
        wet[d2:] += mix[:-d2] * 0.22
        mix += np.convolve(wet, np.ones(12) / 12, "same")
        mix = np.convolve(mix, np.ones(5) / 5, "same")  # Höhen weich machen
        mix[:n] *= np.minimum(1, np.arange(n) / (SR * 1.5))
    elif beat_on and style == "drive":
        # Treibender, dunkler Puls: Sub-Kick auf jedem Schlag, tiefer Bass, Moll-Fläche – keine Höhen
        beat = 60 / bpm
        chords = [[110.0, 130.81, 164.81], [87.31, 110.0, 130.81], [130.81, 164.81, 196.0], [98.0, 123.47, 146.83]]
        bar_len = beat * 4
        b = 0
        while b * bar_len < total + 1:
            xx = tt(bar_len + 0.4)
            ch = chords[b % 4]
            pad = sum(np.sin(2 * np.pi * f * xx) for f in ch) / 3
            pad *= np.minimum(1, xx / 0.6) * np.minimum(1, np.maximum(0, bar_len + 0.4 - xx) / 0.6)
            add(pad, b * bar_len, 0.18)
            for q in range(8):  # pulsierender Achtel-Bass
                xb = tt(beat / 2 * 0.9)
                add(np.sin(2 * np.pi * ch[0] / 2 * xb) * np.exp(-xb * 6), b * bar_len + q * beat / 2, 0.35)
            b += 1
        k = 0
        while k * beat < total:
            x = tt(0.4)
            add(np.sin(2 * np.pi * (40 + 60 * np.exp(-x * 25)) * x) * np.exp(-x * 8), k * beat, 0.75)
            k += 1
        mix = np.convolve(mix, np.ones(8) / 8, "same")
        mix[:n] *= np.minimum(1, np.arange(n) / (SR * 0.2))
    elif beat_on and style == "dark":
        # Dunkle, ruhige Motivations-Fläche: tiefe Moll-Akkorde, weicher Sub-Puls, Hall – keine Höhen
        beat = 60 / bpm
        chords = [[110.0, 130.81, 164.81], [87.31, 110.0, 130.81], [130.81, 164.81, 196.0], [98.0, 123.47, 146.83]]
        bar_len = beat * 4
        b = 0
        while b * bar_len < total + 1:
            xx = tt(bar_len + 0.6)
            ch = chords[b % 4]
            pad = sum(np.sin(2 * np.pi * f * xx) + 0.25 * np.sin(4 * np.pi * f * xx) for f in ch) / 3
            pad += 0.6 * np.sin(2 * np.pi * ch[0] / 2 * xx)
            pad *= np.minimum(1, xx / 1.2) * np.minimum(1, np.maximum(0, bar_len + 0.6 - xx) / 1.0)
            add(pad, b * bar_len, 0.3)
            b += 1
        k = 0
        while k * beat < total:
            x = tt(0.5)
            add(np.sin(2 * np.pi * (38 + 30 * np.exp(-x * 20)) * x) * np.exp(-x * 6), k * beat, 0.55 if k % 2 == 0 else 0.3)
            k += 1
        d1 = int(SR * 0.29)
        wet = np.zeros(n)
        wet[d1:] += mix[:-d1] * 0.3
        mix += np.convolve(wet, np.ones(16) / 16, "same")
        mix = np.convolve(mix, np.ones(6) / 6, "same")
        mix[:n] *= np.minimum(1, np.arange(n) / (SR * 0.8))
    elif beat_on and style == "soft":
        # Weiche Hintergrundmusik: warme Akkord-Flächen + sanfter tiefer Puls, keine Höhen
        beat = 60 / bpm
        chords = [[220, 261.6, 329.6], [174.6, 220, 261.6], [130.8, 196, 261.6], [196, 246.9, 293.7]]
        roots = [55.0, 43.65, 65.41, 49.0]
        bar_len = beat * 4
        b = 0
        while b * bar_len < total:
            xx = tt(bar_len)
            pad = sum(np.sin(2 * np.pi * f * xx) for f in chords[b % 4]) / 3
            pad += 0.5 * np.sin(2 * np.pi * roots[b % 4] * xx)
            pad *= np.minimum(1, xx / 0.8) * np.minimum(1, (bar_len - xx) / 0.6)
            add(pad, b * bar_len, 0.35)
            b += 1
        k = 0
        while k * beat < total:
            if k % 2 == 0:
                x = tt(0.4)
                add(np.sin(2 * np.pi * (40 + 40 * np.exp(-x * 25)) * x) * np.exp(-x * 7), k * beat, 0.6)
            k += 1
        mix[:n] *= np.minimum(1, np.arange(n) / (SR * 0.5))
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

    soft = CLEAN["on"]
    if style == "ambient":
        events = [(k, a) for k, a in events if k in ("whoosh", "ding")]
    for kind, at in events:
        if kind == "glitch":  # kurzes, tiefes Knistern (ohne Höhen)
            x = tt(0.14)
            nz = np.convolve(rng.uniform(-1, 1, len(x)), np.ones(10) / 10, "same")
            add(nz * np.exp(-x * 18) * (np.sin(2 * np.pi * 60 * x) > 0) * 3, at, 0.16)
            continue
        if soft and kind in ("whoosh", "pop", "tick", "blip", "ding", "impact", "riser", "boom"):
            if kind == "whoosh":  # weiches, tiefes Rauschen
                x = tt(0.4)
                nz = np.convolve(rng.uniform(-1, 1, len(x)), np.ones(24) / 24, "same")
                add(nz * np.sin(np.pi * x / 0.4) ** 2 * 3, max(0, at - 0.15), 0.12 if style == "ambient" else 0.25)
            elif kind == "pop":
                x = tt(0.12)
                add(np.sin(2 * np.pi * (220 + 300 * x) * x) * np.exp(-x * 35), at, 0.3)
            elif kind == "tick":  # Holz-Klick statt Piepton
                x = tt(0.05)
                add(np.sin(2 * np.pi * 520 * x) * np.exp(-x * 90), at, 0.22)
            elif kind == "ding":  # weiches Glockenspiel (C5 + G5)
                add(tone([523.25, 783.99], 0.9, 4.5), at, 0.22)
            elif kind == "riser":  # tiefe, ansteigende Spannung (ohne Rauschen in den Höhen)
                x = tt(1.6)
                f = 70 + 160 * (x / 1.6) ** 2
                nz = np.convolve(rng.uniform(-1, 1, len(x)), np.ones(40) / 40, "same") * 6
                add((np.sin(2 * np.pi * np.cumsum(f) / SR) * 0.6 + nz * 0.4) * (x / 1.6) ** 2, at, 0.35)
            elif kind == "boom":
                x = tt(1.0)
                add(np.sin(2 * np.pi * (32 + 70 * np.exp(-x * 14)) * x) * np.exp(-x * 4), at, 0.9)
            elif kind == "impact":
                x = tt(0.7)
                add(np.sin(2 * np.pi * (35 + 70 * np.exp(-x * 18)) * x) * np.exp(-x * 5), at, 0.7)
            continue
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
        elif kind == "growl":
            x = tt(1.0)
            nz = np.convolve(rng.uniform(-1, 1, len(x)), np.ones(30) / 30, "same")
            add(nz * (0.6 + 0.4 * np.sin(2 * np.pi * 28 * x)) * np.sin(np.pi * x) * 4, at, 0.7)
        elif kind == "honk":
            for o in (0, 0.42):
                x = tt(0.32)
                add(np.sign(np.sin(2 * np.pi * 415 * x)) * 0.5 + np.sign(np.sin(2 * np.pi * 520 * x)) * 0.5, at + o, 0.18)
        elif kind == "siren":
            x = tt(3.0)
            f = np.where((x * 1.4).astype(int) % 2 == 0, 760, 960)
            add(np.sin(2 * np.pi * np.cumsum(f) / SR) * np.minimum(1, x * 3) * np.minimum(1, (3 - x) * 3), at, 0.16)
        elif kind == "riser":
            x = tt(2.0)
            add(np.diff(rng.uniform(-1, 1, len(x)), prepend=0) * (x / 2) ** 2, at, 0.5)
        elif kind == "boom":
            x = tt(1.6)
            add(np.sin(2 * np.pi * (30 + 60 * np.exp(-x * 8)) * x) * np.exp(-x * 2.2), at, 1.0)
        elif kind == "vibrate":
            for o in (0, 0.5):
                x = tt(0.3)
                add(np.sin(2 * np.pi * 150 * x) * (0.5 + 0.5 * np.sign(np.sin(2 * np.pi * 25 * x))), at + o, 0.35)
        elif kind == "door":
            x = tt(0.25)
            add(np.sin(2 * np.pi * 90 * x) * np.exp(-x * 25) + noise(0.25, 40) * 0.5, at, 0.7)
        elif kind == "blip":
            add(tone([2400], 0.04, 120), at, 0.18)
        elif kind == "tick":
            add(tone([1800], 0.05, 80), at, 0.4)
        elif kind == "ding":
            add(tone([1046.5, 1568], 0.8, 5), at, 0.45)
            add(tone([1318.5, 2093], 0.6, 6), at + 0.09, 0.35)
    norm = lambda a, lvl: a / (np.max(np.abs(a)) or 1) * lvl
    if CLEAN["on"]:
        # Musik leise, Effekte tiefpassgefiltert, Stimme vorne – ohne Sättigung oder Clipping
        mix = np.convolve(mix, np.ones(6) / 6, "same")
        music, sfx = norm(music, 0.26 if style == "drive" else 0.16), norm(mix, 0.36 if style == "drive" else 0.3)
        v = np.zeros(n)
        if voice is not None and len(voice):
            v[:min(n, len(voice))] = voice[:n]
        win = int(SR * 0.05)
        env = np.sqrt(np.convolve(v ** 2, np.ones(win) / win, "same"))
        env = np.clip(np.convolve(np.clip(env / 0.02, 0, 1), np.ones(int(SR * 0.3)) / int(SR * 0.3), "same") * 1.5, 0, 1)
        out = music * (1 - 0.6 * env) + sfx * (1 - 0.4 * env) + norm(v, 0.85)
        peak = np.max(np.abs(out)) or 1
        if peak > 0.89:
            out *= 0.89 / peak
        return (out * 32767).astype(np.int16)
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

def render(script, out, music=None, beat_on=True, voice_path=None, speed=0.92, speaker=None):
    th = script.get("theme", {})
    C = {"text": rgb(th.get("text", "#ffffff")), "accent": rgb(th.get("accent", "#facc15")),
         "accent_text": rgb(th.get("accent_text", "#111111")), "glow": rgb(th.get("glow", th.get("accent", "#facc15"))),
         "active": rgb(th.get("active", th.get("accent", "#facc15")))}
    bgs = th.get("bgs", [th.get("bg", ["#4c1d95", "#0f0a1f"])])
    bpm = script.get("bpm", 128)
    beat = 60 / bpm
    scenes = script["scenes"]
    for tp_, word in (("quiz", "FRAGE"), ("scan", "SCAN"), ("fact", "FAKT")):
        group = [s for s in scenes if s.get("type") in ((tp_,) if tp_ != "fact" else FACT_TYPES)]
        for i, s in enumerate(group):
            s["_label"] = s.get("label", f"{word} {i + 1}/{len(group)}")
    CLEAN["on"] = script.get("audio", "clean") == "clean"
    CLEAN["calm"] = bool(script.get("calm"))
    clips, vsr = [], None
    if script.get("cast"):
        for sc in scenes:
            sc["_subtitles"] = script.get("subtitles", True)
        clips = plan_cast(scenes, script["cast"], script.get("pronounce"), speed)
        vsr = "sr"
    elif voice_path:
        v = Voice(voice_path, speed, speaker)
        vsr = v.sr
        clips = plan_voice(scenes, v, script.get("pronounce"))
    durs = [dur_of(s) for s in scenes]
    total = sum(durs)
    bg = Background(C, script.get("particles", []))

    # Sound-Events vorab planen
    events, T0 = [], 0.0
    style = script.get("music_style", "soft" if CLEAN["on"] else "beat")
    for i, (sc, d) in enumerate(zip(scenes, durs)):
        tp = sc.get("type")
        if style == "drama":
            if sc.get("fx", {}).get("flash"):
                events.append(("boom", T0))
            elif i:
                events.append(("whoosh", T0))
        else:
            events.append(("impact" if tp in ("hook", "punch") or i == 0 else "whoosh", T0))
        for name, at_ in sc.get("sfx", []):
            events.append((name, T0 + at_))
        if tp == "motion" and i > 0 and sc.get("glitch", True):
            events.append(("glitch", T0))
        if tp == "motion":
            if sc.get("punch"):
                events.append(("boom", T0))
            if sc.get("riser"):
                events.append(("riser", T0 + max(0, d - 1.6)))
            for e in sc.get("els", []):
                if e["k"] == "counter":  # Rattern beim Hochzählen
                    x = e.get("at", 0.2)
                    while x < e.get("at", 0.2) + e.get("dur", 1.6):
                        events.append(("tick", T0 + x)); x += 0.075
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
        if tp in FACT_TYPES and sc.get("_sub_t"):
            events.append(("pop", T0 + sc["_sub_t"]))
        T0 += d

    wav = os.path.splitext(out)[0] + "_audio.wav"
    with wave.open(wav, "wb") as wf:
        wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(SR)
        if vsr == "sr":
            vb = voice_bus_sr(clips, total) if clips else None
        else:
            vb = voice_bus(clips, vsr, total, script.get("pitch", 0.0)) if clips else None
        wf.writeframes(synth_audio(total, events, bpm, beat_on, music, voice=vb, style=style).tobytes())

    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
           "-r", str(FPS), "-i", "-", "-i", wav, "-map", "0:v", "-map", "1:a",
           "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-b:a", "192k", "-ac", "2", "-t", f"{total:.3f}", "-movflags", "+faststart", out]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    total_frames = int(total * FPS)
    header = script.get("header")
    fxcache = {}
    last_frame = None
    fr, T0 = 0, 0.0
    for si, (sc, d) in enumerate(zip(scenes, durs)):
        tp = sc.get("type")
        sbg = sc.get("bg", bgs[si % len(bgs)]) if tp != "cartoon" else bgs[0]
        rays = 1.0 if tp in ("hook", "punch", "cta") else (0.5 if tp in FACT_TYPES else 0.0)
        fn = SCENES[tp]
        for i in range(int(round(d * FPS))):
            t = i / FPS
            T = fr / FPS
            think = sc.get("think", 2.6 if tp == "quiz" else 2.2)
            quiz_rays = 1.0 if tp in ("quiz", "scan") and t >= think else 0.0
            calm = bool(script.get("calm"))
            img = bg.render(T, sbg, beat, 0.0 if calm else max(rays, quiz_rays), calm, script.get("backdrop"))
            ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            fn(ov, sc, t, d, C, events)
            # Kamera: Zoom-Punch beim Schnitt, Wackeln bei Impact, leichtes Atmen im Beat
            zoom = 1 + 0.10 * (1 - ease_out(t / 0.25)) + 0.012 * math.exp(-((T % beat) / beat) * 5)
            shake = 22 * max(0, 1 - t / 0.3) if tp in ("hook", "punch") else 0
            if tp == "motion":
                zoom = 1 + 0.04 * (t / max(d, 0.1))
                shake = 16 * max(0, 1 - t / 0.3) if sc.get("punch") else 0
            if calm:  # ruhige Kamera: nur ganz sanftes Heranzoomen, kein Wackeln
                zoom = 1 + 0.025 * (t / max(d, 0.1))
                shake = 0
            if tp in ("story", "cartoon"):  # langsamer Kamera-Zoom statt Beat-Pumpen
                zoom = 1 + 0.06 * (t / max(d, 0.1)) + 0.04 * (1 - ease_out(t / 0.4))
                shake = sc.get("fx", {}).get("shake", 0) * 26 * max(0.15, 1 - t / 0.6)
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
            if script.get("cinematic") or tp in ("story", "cartoon"):
                story_overlay(img, sc, t, fxcache, grain=bool(script.get("cinematic")))
            dr = ImageDraw.Draw(img)
            dr.rectangle([0, 0, W, 12], fill=(0, 0, 0, 90))
            dr.rectangle([0, 0, W * (fr + 1) / total_frames, 12], fill=C["accent"] + (255,))
            if header:
                hw = word_img(header, 58, "normal", C)
                paste_scaled(img, hw, W / 2, 200)
            if script.get("title_bar"):
                ft = font("black", 62)
                tb = script["title_bar"].upper()
                tw = ft.getlength(tb)
                dr.rectangle([W / 2 - tw / 2 - 28, 165, W / 2 + tw / 2 + 28, 255], fill=(255, 255, 255, 255))
                dr.text((W / 2, 210), tb, font=ft, fill=(10, 10, 10, 255), anchor="mm")
            frame = img.convert("RGB")
            if tp in ("hook", "punch") and t < 0.1 and not calm:
                frame = Image.blend(frame, Image.new("RGB", (W, H), (255, 255, 255)), 0.55 * (1 - t / 0.1))
            if tp == "motion" and si > 0 and t < 0.16 and sc.get("glitch", True):
                import motion
                frame = motion.glitch(frame, t, si)
            if calm and t < 0.3 and fr > 0:  # weiche Überblendung statt harter Schnitte
                frame = Image.blend(last_frame, frame, t / 0.3)
            last_frame = frame
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
    ap.add_argument("--voice", help="Stimme, z. B. thorsten-high, thorsten_emotional:amused, kerstin oder Pfad zu .onnx")
    ap.add_argument("--no-voice", action="store_true", help="ohne Vorlese-Stimme")
    ap.add_argument("--speed", type=float, default=None, help="Sprechtempo (<1 = schneller), Standard 0.92")
    a = ap.parse_args()
    with open(a.script, encoding="utf-8") as f:
        script = json.load(f)
    out = a.out or os.path.join(HERE, "output", os.path.splitext(os.path.basename(a.script))[0] + ".mp4")
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    voice_path, speaker = None, None
    if not a.no_voice and script.get("voice", "thorsten-high") != "none":
        name = a.voice or script.get("voice", "thorsten-high")
        if ":" in name:
            name, speaker = name.split(":", 1)
        voice_path = name
        if not name.endswith(".onnx"):
            for cand in (f"de_DE-{name}-high.onnx", f"de_DE-{name}-medium.onnx", f"de_DE-{name}.onnx",
                         f"de-{name}-low.onnx", f"de-{name}.onnx"):
                voice_path = os.path.join(HERE, "voices", cand)
                if os.path.exists(voice_path):
                    break
        if not os.path.exists(voice_path):
            print(f"Stimme nicht gefunden: {voice_path} (tiktok/get_voices.sh ausführen). Ohne Stimme weiter.",
                  file=sys.stderr)
            voice_path = None
    render(script, out, a.music, not a.no_beat, voice_path, a.speed or script.get("speed", 0.92), speaker)


if __name__ == "__main__":
    main()
