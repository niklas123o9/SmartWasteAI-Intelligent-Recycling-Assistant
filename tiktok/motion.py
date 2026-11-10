"""Minimalistische, dunkle Motion-Grafik (Motivations-Stil): große Überschrift mit Überzeile,
leuchtende Figuren, Zähler, Kurven, Chips und Glitch-Übergänge."""
import math

from PIL import Image, ImageDraw, ImageFilter

W, H = 1080, 1920
COLORS = {"white": (245, 245, 245), "red": (255, 82, 82), "green": (74, 222, 128), "yellow": (250, 204, 21),
          "gray": (120, 120, 128), "blue": (96, 165, 250)}


def col(c):
    if isinstance(c, (tuple, list)):
        return tuple(c)
    if c in COLORS:
        return COLORS[c]
    c = c.lstrip("#")
    return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))


def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def ease(t):
    t = clamp(t)
    return 1 - (1 - t) ** 3


_F = {}


def font(size, weight="black"):
    from PIL import ImageFont
    key = (size, weight)
    if key not in _F:
        name = {"black": "Inter-Black.otf", "bold": "Inter-Bold.otf", "medium": "Inter-Medium.otf"}[weight]
        try:
            _F[key] = ImageFont.truetype("/usr/share/fonts/opentype/inter/" + name, size)
        except OSError:
            _F[key] = ImageFont.load_default(size)
    return _F[key]


def background():
    """Fast schwarz, minimaler Verlauf + Vignette."""
    if "bg" not in _F:
        import numpy as np
        yy, xx = np.mgrid[0:H // 4, 0:W // 4]
        r = np.sqrt(((xx - W / 8) / (W / 8)) ** 2 + ((yy - H / 9) / (H / 7)) ** 2)
        base = np.clip(22 - r * 10, 8, 22)
        im = np.dstack([base, base, base + 2]).astype("uint8")
        _F["bg"] = Image.fromarray(im, "RGB").resize((W, H), Image.BICUBIC).convert("RGBA")
    return _F["bg"].copy()


def glow_layer(draw_fn, radius=18, strength=2):
    """Zeichnet etwas scharf + mit weichem Leuchten."""
    sharp = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw_fn(ImageDraw.Draw(sharp))
    small = sharp.resize((W // 3, H // 3), Image.BILINEAR).filter(ImageFilter.GaussianBlur(radius / 3))
    glow = small.resize((W, H), Image.BILINEAR)
    out = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    for _ in range(strength):
        out.alpha_composite(glow)
    out.alpha_composite(sharp)
    return out


# ---------------------------------------------------------------- Text

def headline(img, t, over, head, color="white", y=400, reveal=0.35, punch=False, size=124):
    """Überzeile + große Überschrift. Wörter erscheinen nacheinander (synchron zur Stimme).
    '|' trennt Zeilen, Wörter in [eckigen Klammern] bekommen die Akzentfarbe."""
    d = ImageDraw.Draw(img)
    if over:
        f = font(36, "bold")
        txt = " ".join(over.upper())
        a = int(190 * ease(t / 0.2))
        d.text((W / 2, y - 105), txt, font=f, fill=(160, 160, 168, a), anchor="mm")
    if not head:
        return
    lines = head.upper().split("|")
    words_total = sum(len(l.split()) for l in lines)
    shown = words_total if reveal <= 0.06 else int(words_total * clamp(t / reveal) + 0.999)
    f = font(size)
    plain = [l.replace("[", "").replace("]", "") for l in lines]
    while max(f.getlength(l) for l in plain) > W - 120 and size > 56:
        size -= 6
        f = font(size)
    lh = int(size * 1.2)
    layer = Image.new("RGBA", (W, lh * len(lines) + 60), (0, 0, 0, 0))
    ld = ImageDraw.Draw(layer)
    idx = 0
    for li, line in enumerate(lines):
        words = line.split()
        lw = f.getlength(" ".join(w.replace("[", "").replace("]", "") for w in words))
        x = (W - lw) / 2
        for w in words:
            marked = "[" in w or "]" in w
            ww = w.replace("[", "").replace("]", "")
            if idx < shown:
                c = col(color if color != "white" else "yellow") if marked else col(color)
                ld.text((x, 30 + li * lh), ww, font=f, fill=c + (255,))
            x += f.getlength(ww + " ")
            idx += 1
    if punch:
        k = ease(t / 0.18)
        sc = 1.35 - 0.35 * k
        layer = layer.resize((int(layer.width * sc), int(layer.height * sc)), Image.BILINEAR)
    lx = int((W - layer.width) / 2)
    ly = int(y - 30 - lh / 2 - (layer.height - (lh * len(lines) + 60)) / 2)
    g = layer.filter(ImageFilter.GaussianBlur(16))
    if color != "white":
        img.alpha_composite(g, (lx, ly))
    img.alpha_composite(layer, (lx, ly))


def el_money(img, e, t):
    """Geldscheine: 'rain' = regnen von oben, 'away' = fliegen davon."""
    import random
    rnd = random.Random(5)
    d_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(d_layer)
    n = e.get("n", 26)
    for i in range(n):
        x0, sp, ph, delay = rnd.uniform(60, W - 60), rnd.uniform(380, 700), rnd.uniform(0, 6.3), rnd.uniform(0, 1.2)
        tt = t - e.get("at", 0) - delay * 0.5
        if tt < 0:
            continue
        if e.get("mode", "rain") == "rain":
            x, y = x0 + math.sin(tt * 2 + ph) * 40, -80 + tt * sp
        else:
            x, y = W / 2 + (x0 - W / 2) * tt * 1.6, e.get("y", 1050) - tt * sp * 0.9
        if y > H + 80 or y < -120:
            continue
        ang = math.sin(tt * 3 + ph) * 35
        bill = Image.new("RGBA", (120, 64), (0, 0, 0, 0))
        bd = ImageDraw.Draw(bill)
        bd.rounded_rectangle([2, 2, 118, 62], radius=8, fill=(34, 120, 70, 235), outline=(74, 222, 128, 255), width=4)
        bd.text((60, 33), "€", font=font(36), fill=(190, 255, 210, 255), anchor="mm")
        bill = bill.rotate(ang, expand=True, resample=Image.BICUBIC)
        d_layer.alpha_composite(bill, (int(x - bill.width / 2), int(y - bill.height / 2)))
    img.alpha_composite(d_layer)


# ---------------------------------------------------------------- Figuren

def figure(d, cx, ground, h=260, c=(240, 240, 240), a=255):
    """Schlichte Pillen-Figur: Kopf + Körper + Beine."""
    r = h * 0.085
    d.ellipse([cx - r, ground - h, cx + r, ground - h + 2 * r], fill=c + (a,))
    bw = h * 0.17
    d.rounded_rectangle([cx - bw / 2, ground - h + 2.3 * r, cx + bw / 2, ground - h * 0.38], radius=int(bw / 2),
                        fill=c + (a,))
    lw = max(3, int(h * 0.04))
    d.line([(cx - bw * 0.22, ground - h * 0.4), (cx - bw * 0.25, ground)], fill=c + (a,), width=lw)
    d.line([(cx + bw * 0.22, ground - h * 0.4), (cx + bw * 0.25, ground)], fill=c + (a,), width=lw)


def pill_label(d, cx, cy, text, c, a=255):
    f = font(30, "black")
    tw = f.getlength(text)
    d.rounded_rectangle([cx - tw / 2 - 18, cy - 24, cx + tw / 2 + 18, cy + 24], radius=24, outline=c + (a,), width=4,
                        fill=(c[0] // 6, c[1] // 6, c[2] // 6, int(a * 0.8)))
    d.text((cx, cy + 1), text, font=f, fill=c + (a,), anchor="mm")


def el_figures(img, e, t):
    n = e.get("n", 5)
    hi = e.get("hi", [])
    ground = e.get("y", 1200)
    span = e.get("span", 760)
    h = e.get("h", 260)
    xs = [W / 2 + (i - (n - 1) / 2) * span / max(1, n - 1) for i in range(n)] if n > 1 else [W / 2]
    if e.get("floor", True):
        ImageDraw.Draw(img).line([(80, ground + 4), (W - 80, ground + 4)], fill=(70, 70, 76, 255), width=4)

    def dr(d):
        for i, x in enumerate(xs):
            k = ease((t - e.get("at", 0) - i * 0.06) / 0.3)
            if k <= 0:
                continue
            if i in hi:
                c = col(e.get("hi_color", "white"))
                figure(d, x, ground, h * 1.08, c, int(255 * k))
            else:
                figure(d, x, ground, h, (110, 110, 118), int(255 * k))
    img.alpha_composite(glow_layer(dr, 22, 2))
    d = ImageDraw.Draw(img)
    for i, x in enumerate(xs):
        lab = (e.get("labels") or [None] * n)[i]
        if lab:
            k = ease((t - e.get("label_at", 0.5) - i * 0.08) / 0.25)
            if k > 0:
                pill_label(d, x, ground - h - 70, lab, col(e.get("label_color", "red")), int(255 * k))
    if e.get("x_on") is not None and t > e.get("x_at", 1.0):
        x = xs[e["x_on"]]
        k = ease((t - e.get("x_at", 1.0)) / 0.2)
        s = 90 * k
        y = ground - h / 2
        d.line([(x - s, y - s), (x + s, y + s)], fill=COLORS["red"] + (255,), width=16)
        d.line([(x - s, y + s), (x + s, y - s)], fill=COLORS["red"] + (255,), width=16)


def el_counter(img, e, t):
    k = ease((t - e.get("at", 0.2)) / e.get("dur", 1.6))
    v = e["from"] + (e["to"] - e["from"]) * k
    dec = e.get("dec", 0)
    txt = f"{v:,.{dec}f}".replace(",", "X").replace(".", ",").replace("X", ".") + e.get("suffix", "")
    c = col(e.get("color", "green"))
    layer = Image.new("RGBA", (W, 300), (0, 0, 0, 0))
    ImageDraw.Draw(layer).text((W / 2, 150), txt, font=font(e.get("size", 190)), fill=c + (255,), anchor="mm")
    y = e.get("y", 800)
    img.alpha_composite(layer.filter(ImageFilter.GaussianBlur(18)), (0, y - 150))
    img.alpha_composite(layer, (0, y - 150))
    if e.get("caption"):
        ImageDraw.Draw(img).text((W / 2, y + 130), e["caption"], font=font(40, "bold"), fill=(160, 160, 168, 255),
                                 anchor="mm")


def el_curve(img, e, t):
    """Kurve, die sich aufbaut (z. B. 1,01^x oder 0,99^x)."""
    x0, x1 = 140, W - 140
    y0, y1 = e.get("top", 640), e.get("bottom", 1180)
    d = ImageDraw.Draw(img)
    d.line([(x0, y1), (x1, y1)], fill=(70, 70, 76, 255), width=4)
    d.line([(x0, y0), (x0, y1)], fill=(70, 70, 76, 255), width=4)
    k = ease((t - e.get("at", 0.2)) / e.get("dur", 2.0))
    curves = e.get("curves", [{"base": 1.01, "color": "green"}])
    vmax = max([1.0] + [c["base"] ** 365 for c in curves])
    for c in curves:
        pts = []
        for i in range(int(120 * k) + 1):
            day = 365 * i / 120
            v = c["base"] ** day
            pts.append((x0 + (x1 - x0) * i / 120, y1 - (y1 - y0) * (v / vmax) * 0.95 - (8 if c["base"] < 1 else 0)))
        if len(pts) > 1:
            cc = col(c["color"])
            img.alpha_composite(glow_layer(lambda dd: dd.line(pts, fill=cc + (255,), width=9, joint="curve"), 16, 2))
            if c.get("label") and k > 0.95:
                d.text((pts[-1][0] - 10, pts[-1][1] - 40), c["label"], font=font(44), fill=cc + (255,), anchor="rm")
    d.text((x1, y1 + 40), "365 TAGE", font=font(30, "bold"), fill=(130, 130, 138, 255), anchor="rm")


def el_chips(img, e, t):
    d = ImageDraw.Draw(img)
    for i, ch in enumerate(e["items"]):
        k = ease((t - e.get("at", 0.3) - i * 0.25) / 0.25)
        if k <= 0:
            continue
        cx, cy = ch.get("x", 0.5) * W, ch.get("y", 0.45) * H + math.sin(t * 2 + i) * 6
        c = col(ch.get("color", "white"))
        f = font(ch.get("size", 46), "black")
        tw = f.getlength(ch["t"])
        a = int(255 * k)
        d.rounded_rectangle([cx - tw / 2 - 28, cy - 42, cx + tw / 2 + 28, cy + 42], radius=22,
                            fill=(c[0] // 7, c[1] // 7, c[2] // 7, a), outline=c + (a,), width=4)
        d.text((cx, cy + 2), ch["t"], font=f, fill=c + (a,), anchor="mm")
        if ch.get("strike") and t > ch.get("strike_at", 1.2):
            kk = ease((t - ch.get("strike_at", 1.2)) / 0.2)
            d.line([(cx - tw / 2 - 30, cy), (cx - tw / 2 - 30 + (tw + 60) * kk, cy)], fill=COLORS["red"] + (255,),
                   width=10)


def el_fork(img, e, t):
    """Eine Figur, zwei Wege: einer steigt (grün), einer fällt (rot)."""
    sx, sy = W / 2, e.get("y", 1050)
    k = ease((t - e.get("at", 0.4)) / 1.4)
    up = [(sx + i * 3.6, sy - 150 - 330 * (i / 100) ** 2) for i in range(int(100 * k) + 1)]
    dn = [(sx - i * 3.6, sy - 20 + 170 * (i / 100) ** 1.4) for i in range(int(100 * k) + 1)]

    def dr(d):
        if len(up) > 1:
            d.line(up, fill=COLORS["green"] + (255,), width=9)
            d.line(dn, fill=COLORS["red"] + (255,), width=9)
        figure(d, sx, sy, 200, (245, 245, 245), 255)
    img.alpha_composite(glow_layer(dr, 16, 2))
    d = ImageDraw.Draw(img)
    if k > 0.9:
        d.text((up[-1][0], up[-1][1] - 50), e.get("up", "+1 %"), font=font(50), fill=COLORS["green"] + (255,), anchor="mm")
        d.text((dn[-1][0], dn[-1][1] + 50), e.get("down", "−1 %"), font=font(50), fill=COLORS["red"] + (255,), anchor="mm")


def el_stairs(img, e, t):
    """Figur steigt Stufe für Stufe hoch."""
    n = e.get("steps", 6)
    x0, base, sw, shh = 170, e.get("y", 1250), 125, 75
    k = (t - e.get("at", 0.3)) / e.get("dur", 2.2)
    pos = clamp(k) * (n - 1)

    def dr(d):
        for i in range(n):
            d.rectangle([x0 + i * sw, base - (i + 1) * shh, x0 + (i + 1) * sw, base], outline=(90, 90, 98, 255), width=4)
        i = int(pos)
        frac = pos - i
        x = x0 + (i + frac) * sw + sw / 2
        y = base - (i + 1) * shh - (math.sin(frac * math.pi) * 30 if frac > 0 else 0)
        figure(d, x, y, 170, col(e.get("color", "green")), 255)
    img.alpha_composite(glow_layer(dr, 16, 2))


ELEMENTS = {"figures": el_figures, "counter": el_counter, "curve": el_curve, "chips": el_chips, "fork": el_fork,
            "stairs": el_stairs, "money": el_money}


def render_scene(sc, t, d):
    img = background()
    for e in sc.get("els", []):
        ELEMENTS[e["k"]](img, e, t)
    rev = 0.05 if sc.get("punch") else max(0.2, sc.get("_say_dur", 1.0) * 0.85)
    empty = not sc.get("els")
    headline(img, t, sc.get("over"), sc.get("head"), sc.get("color", "white"),
             sc.get("head_y", 880 if empty else 400), rev, sc.get("punch", False), sc.get("size", 190 if empty else 124))
    if sc.get("flash") and t < 0.22:
        c = col(sc["flash"])
        img.alpha_composite(Image.new("RGBA", (W, H), c + (int(120 * (1 - t / 0.22)),)))
    return img


def glitch(frame, t, seed=0):
    """Kurzer Glitch-Übergang: verschobene Streifen + Farbversatz."""
    import random
    rnd = random.Random(int(t * 1000) + seed)
    out = frame.copy()
    k = 1 - t / 0.16
    for _ in range(int(14 * k) + 2):
        y = rnd.randint(0, H - 60)
        hgt = rnd.randint(8, 70)
        dx = int(rnd.uniform(-120, 120) * k)
        strip = frame.crop((0, y, W, y + hgt))
        out.paste(strip, (dx, y))
    r, g, b = out.split()[:3]
    off = int(14 * k)
    r = r.transform(r.size, Image.AFFINE, (1, 0, off, 0, 1, 0))
    b = b.transform(b.size, Image.AFFINE, (1, 0, -off, 0, 1, 0))
    return Image.merge("RGB", (r, g, b))
