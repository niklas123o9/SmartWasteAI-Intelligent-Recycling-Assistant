#!/usr/bin/env python3
"""TikTok-Video-Generator (1080x1920, 30 fps, H.264).

Erstellt aus einem einfachen JSON-Skript ein fertiges Hochkant-Video mit
animiertem Text, Farbverlauf-Hintergrund und Fortschrittsbalken.

Benutzung:
    python3 tiktok/make_video.py tiktok/scripts/01_falsche_tonne.json
    python3 tiktok/make_video.py skript.json -o mein_video.mp4 --music song.mp3

Benötigt: Python 3, Pillow (pip install pillow), ffmpeg.
Text mit *Sternchen* wird in der Akzentfarbe hervorgehoben.
"""
import argparse
import json
import math
import os
import subprocess
import sys

from PIL import Image, ImageDraw, ImageFont

W, H, FPS = 1080, 1920, 30
MARGIN_X = 100            # TikTok-UI rechts/links freihalten
SAFE_TOP, SAFE_BOTTOM = 260, 1450  # unten liegen Caption & Buttons
FADE_FRAMES = 8

FONT_DIRS = [
    os.path.join(os.path.dirname(__file__), "fonts"),
    "/usr/share/fonts/opentype/inter",
    "/usr/share/fonts/truetype/dejavu",
    "/Library/Fonts", "C:/Windows/Fonts",
]
FONT_FILES = {
    "black": ["Inter-Black.otf", "Inter-ExtraBold.otf", "DejaVuSans-Bold.ttf", "arialbd.ttf", "Arial Bold.ttf"],
    "bold": ["Inter-Bold.otf", "DejaVuSans-Bold.ttf", "arialbd.ttf", "Arial Bold.ttf"],
    "regular": ["Inter-Medium.otf", "Inter-Regular.otf", "DejaVuSans.ttf", "arial.ttf", "Arial.ttf"],
}
_font_cache = {}


def font(weight, size):
    key = (weight, size)
    if key not in _font_cache:
        for d in FONT_DIRS:
            for f in FONT_FILES[weight]:
                p = os.path.join(d, f)
                if os.path.exists(p):
                    _font_cache[key] = ImageFont.truetype(p, size)
                    break
            if key in _font_cache:
                break
        else:
            _font_cache[key] = ImageFont.load_default(size)
    return _font_cache[key]


def hex_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def ease_out(t):
    t = max(0.0, min(1.0, t))
    return 1 - (1 - t) ** 3


def ease_back(t):
    t = max(0.0, min(1.0, t))
    c = 1.7
    return 1 + (c + 1) * (t - 1) ** 3 + c * (t - 1) ** 2


# ---------- Hintergrund ----------

def gradient(c1, c2):
    top, bot = hex_rgb(c1), hex_rgb(c2)
    col = Image.new("RGB", (1, H))
    for y in range(H):
        t = y / (H - 1)
        col.putpixel((0, y), tuple(int(top[i] + (bot[i] - top[i]) * t) for i in range(3)))
    return col.resize((W, H))


def draw_blobs(img, accent, t):
    """Zwei weiche, langsam schwebende Kreise für Bewegung im Hintergrund."""
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    r, g, b = accent
    for i, (cx, cy, rad, sp) in enumerate([(0.15, 0.2, 420, 0.35), (0.9, 0.78, 520, 0.27)]):
        x = cx * W + math.sin(t * sp + i) * 90
        y = cy * H + math.cos(t * sp * 1.3 + i) * 120
        d.ellipse([x - rad, y - rad, x + rad, y + rad], fill=(r, g, b, 26))
    img.alpha_composite(ov)


# ---------- Text-Layout ----------

def parse_words(text):
    """'Das ist *wichtig*' -> [('Das', False), ('ist', False), ('wichtig', True)]"""
    out = []
    for line in text.split("\n"):
        for w in line.split():
            hl = w.startswith("*") or w.endswith("*") or w.endswith("*,") or w.endswith("*.")
            out.append((w.replace("*", ""), hl))
        out.append(("\n", False))
    return out[:-1]


def layout(text, fnt, max_w, line_gap=1.18):
    words = parse_words(text)
    space = fnt.getlength(" ")
    lines, cur, cur_w = [], [], 0
    for w, hl in words:
        if w == "\n":
            lines.append(cur); cur, cur_w = [], 0
            continue
        ww = fnt.getlength(w)
        if cur and cur_w + space + ww > max_w:
            lines.append(cur); cur, cur_w = [], 0
        cur.append((w, hl, ww))
        cur_w += (space if cur_w else 0) + ww
    if cur:
        lines.append(cur)
    asc, desc = fnt.getmetrics()
    lh = int((asc + desc) * line_gap)
    placed = []
    for li, line in enumerate(lines):
        lw = sum(x[2] for x in line) + space * (len(line) - 1)
        x = (W - lw) / 2
        for w, hl, ww in line:
            placed.append({"w": w, "hl": hl, "x": x, "y": li * lh})
            x += ww + space
    return placed, len(lines) * lh


def fit_font(text, weight, size, max_w, max_h):
    while size > 30:
        f = font(weight, size)
        _, h = layout(text, f, max_w)
        longest = max((f.getlength(w) for w, _ in parse_words(text) if w != "\n"), default=0)
        if h <= max_h and longest <= max_w:
            return f
        size -= 4
    return font(weight, size)


def draw_words(ov, placed, fnt, top, t, start, per_word, colors, pop=False, shadow=True):
    d = ImageDraw.Draw(ov)
    for i, p in enumerate(placed):
        k = (t - start - i * per_word) / 0.25
        if k <= 0:
            continue
        e = ease_back(k) if pop else ease_out(k)
        a = int(255 * min(1.0, k * 1.5))
        dy = (1 - e) * 40
        col = colors["accent"] if p["hl"] else colors["text"]
        y = top + p["y"] + dy
        if shadow:
            d.text((p["x"] + 4, y + 6), p["w"], font=fnt, fill=(0, 0, 0, int(a * 0.35)))
        d.text((p["x"], y), p["w"], font=fnt, fill=col + (a,))


# ---------- Szenen ----------

def scene_hook(ov, sc, t, dur, colors):
    f = fit_font(sc["text"], "black", sc.get("size", 132), W - 2 * MARGIN_X, 800)
    placed, h = layout(sc["text"], f, W - 2 * MARGIN_X, 1.08)
    top = (SAFE_TOP + SAFE_BOTTOM) / 2 - h / 2
    pw = min(0.18, (dur * 0.5) / max(1, len(placed)))
    draw_words(ov, placed, f, top, t, 0.1, pw, colors, pop=True)
    if sc.get("sub"):
        fs = font("regular", 52)
        sp, _ = layout(sc["sub"], fs, W - 2 * MARGIN_X)
        draw_words(ov, sp, fs, top + h + 50, t, 0.4 + len(placed) * pw, 0.03, colors, shadow=False)


def scene_text(ov, sc, t, dur, colors):
    d = ImageDraw.Draw(ov)
    y = SAFE_TOP + 80
    if sc.get("label"):
        fl = font("bold", 44)
        txt = sc["label"].upper()
        tw = fl.getlength(txt)
        k = ease_out(t / 0.4)
        x0 = (W - tw) / 2 - 30
        d.rounded_rectangle([x0, y, x0 + (tw + 60) * k, y + 76], radius=38, fill=colors["accent"] + (255,))
        if k > 0.9:
            d.text(((W - tw) / 2, y + 12), txt, font=fl, fill=colors["bg_dark"] + (255,))
        y += 140
    if sc.get("headline"):
        fh = fit_font(sc["headline"], "black", sc.get("size", 104), W - 2 * MARGIN_X, 520)
        placed, h = layout(sc["headline"], fh, W - 2 * MARGIN_X, 1.08)
        draw_words(ov, placed, fh, y, t, 0.15, 0.09, colors, pop=True)
        y += h + 60
        start = 0.3 + len(placed) * 0.09
    else:
        start = 0.2
    if sc.get("body"):
        fb = fit_font(sc["body"], "regular", sc.get("body_size", 62), W - 2 * MARGIN_X, SAFE_BOTTOM - y)
        placed, _ = layout(sc["body"], fb, W - 2 * MARGIN_X, 1.3)
        pw = min(0.12, max(0.02, (dur - start - 1.2) / max(1, len(placed))))
        draw_words(ov, placed, fb, y, t, start, pw, colors, shadow=False)


def scene_list(ov, sc, t, dur, colors):
    d = ImageDraw.Draw(ov)
    fh = fit_font(sc["headline"], "black", sc.get("size", 92), W - 2 * MARGIN_X, 330)
    placed, h = layout(sc["headline"], fh, W - 2 * MARGIN_X, 1.08)
    y = SAFE_TOP + 60
    draw_words(ov, placed, fh, y, t, 0.1, 0.07, colors, pop=True)
    y += h + 70
    items = sc["items"]
    step = min(1.2, (dur - 1.5) / max(1, len(items)))
    fi = font("bold", sc.get("item_size", 54))
    row_h = min(230, (SAFE_BOTTOM - y) / max(1, len(items)))
    for i, item in enumerate(items):
        st = 0.6 + i * step
        k = (t - st) / 0.35
        if k <= 0:
            continue
        e = ease_back(k)
        a = int(255 * min(1, k * 2))
        cy = y + i * row_h
        dx = (1 - ease_out(k)) * -120
        r = 48 * min(1.15, e)
        cx = MARGIN_X + 50 + dx
        d.ellipse([cx - r, cy + 50 - r, cx + r, cy + 50 + r], fill=colors["accent"] + (a,))
        num = str(i + 1) if not sc.get("icons") else sc["icons"][i]
        fn = font("black", 50)
        d.text((cx - fn.getlength(num) / 2, cy + 20), num, font=fn, fill=colors["bg_dark"] + (a,))
        tx = MARGIN_X + 130 + dx
        max_w = W - MARGIN_X - (MARGIN_X + 130)
        lh = int(sum(fi.getmetrics()) * 1.1)
        x, ly = tx, cy + 18
        for w, hl in parse_words(item):
            if w == "\n":
                x, ly = tx, ly + lh
                continue
            ww = fi.getlength(w)
            if x > tx and x - tx + ww > max_w:
                x, ly = tx, ly + lh
            d.text((x, ly), w, font=fi, fill=(colors["accent"] if hl else colors["text"]) + (a,))
            x += ww + fi.getlength(" ")


def scene_cta(ov, sc, t, dur, colors):
    scene_hook(ov, {"text": sc["text"], "size": sc.get("size", 112)}, t, dur, colors)
    if sc.get("button"):
        d = ImageDraw.Draw(ov)
        fb = font("black", 58)
        txt = sc["button"]
        tw = fb.getlength(txt)
        k = ease_back((t - 1.0) / 0.4)
        if k > 0:
            pulse = 1 + 0.04 * math.sin(t * 6)
            bw, bh = (tw + 110) * k * pulse, 120 * k * pulse
            cx, cy = W / 2, SAFE_BOTTOM - 110
            d.rounded_rectangle([cx - bw / 2, cy - bh / 2, cx + bw / 2, cy + bh / 2], radius=60,
                                fill=colors["accent"] + (255,))
            if k > 0.8:
                d.text((cx - tw / 2, cy - 38), txt, font=fb, fill=colors["bg_dark"] + (255,))


SCENES = {"hook": scene_hook, "text": scene_text, "list": scene_list, "cta": scene_cta}


# ---------- Rendern ----------

def render(script, out_path, music=None, music_volume=0.25):
    theme = script.get("theme", {})
    bg = theme.get("bg", ["#14532d", "#052e16"])
    colors = {
        "text": hex_rgb(theme.get("text", "#ffffff")),
        "accent": hex_rgb(theme.get("accent", "#4ade80")),
        "bg_dark": hex_rgb(bg[1]),
    }
    scenes = script["scenes"]
    total = sum(s.get("duration", 4) for s in scenes)
    total_frames = int(total * FPS)
    handle = script.get("handle", "")
    fh = font("bold", 40)

    audio_in = ["-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo"]
    audio_map = ["-map", "1:a"]
    if music:
        audio_in = ["-stream_loop", "-1", "-i", music]
        audio_map = ["-map", "1:a", "-af", f"volume={music_volume},afade=t=out:st={max(0, total - 1.5)}:d=1.5"]

    cmd = ["ffmpeg", "-y", "-loglevel", "error",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
           *audio_in, "-map", "0:v", *audio_map,
           "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-b:a", "192k", "-t", f"{total:.3f}", "-movflags", "+faststart", out_path]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)

    frame_no = 0
    prev_last = None
    for si, sc in enumerate(scenes):
        dur = sc.get("duration", 4)
        n = int(round(dur * FPS))
        sbg = sc.get("bg", bg)
        base = gradient(*sbg).convert("RGBA")
        fn = SCENES[sc.get("type", "text")]
        last = None
        for i in range(n):
            t = i / FPS
            img = base.copy()
            draw_blobs(img, colors["accent"], frame_no / FPS)
            ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            fn(ov, sc, t, dur, colors)
            # Fortschrittsbalken + Handle
            d = ImageDraw.Draw(ov)
            d.rounded_rectangle([MARGIN_X, 150, W - MARGIN_X, 160], radius=5, fill=(255, 255, 255, 60))
            px = MARGIN_X + (W - 2 * MARGIN_X) * (frame_no + 1) / total_frames
            d.rounded_rectangle([MARGIN_X, 150, px, 160], radius=5, fill=colors["accent"] + (255,))
            if handle:
                d.text(((W - fh.getlength(handle)) / 2, 185), handle, font=fh, fill=(255, 255, 255, 170))
            img.alpha_composite(ov)
            frame = img.convert("RGB")
            if prev_last is not None and i < FADE_FRAMES:
                frame = Image.blend(prev_last, frame, (i + 1) / (FADE_FRAMES + 1))
            proc.stdin.write(frame.tobytes())
            last = frame
            frame_no += 1
        prev_last = last
        print(f"  Szene {si + 1}/{len(scenes)} fertig", file=sys.stderr)
    proc.stdin.close()
    if proc.wait() != 0:
        sys.exit("ffmpeg ist fehlgeschlagen")

    caption = script.get("caption")
    if caption:
        with open(os.path.splitext(out_path)[0] + "_caption.txt", "w", encoding="utf-8") as f:
            f.write(caption.strip() + "\n")
    print(f"Fertig: {out_path} ({total:.1f}s)")


def main():
    ap = argparse.ArgumentParser(description="Erstellt ein TikTok-Video aus einem JSON-Skript.")
    ap.add_argument("script")
    ap.add_argument("-o", "--out")
    ap.add_argument("--music", help="optionale Audiodatei (mp3/wav) als Hintergrundmusik")
    ap.add_argument("--music-volume", type=float, default=0.25)
    a = ap.parse_args()
    with open(a.script, encoding="utf-8") as f:
        script = json.load(f)
    out = a.out or os.path.join(os.path.dirname(os.path.abspath(__file__)), "output",
                                os.path.splitext(os.path.basename(a.script))[0] + ".mp4")
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    render(script, out, a.music, a.music_volume)


if __name__ == "__main__":
    main()
