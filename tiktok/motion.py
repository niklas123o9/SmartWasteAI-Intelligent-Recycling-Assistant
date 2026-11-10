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

def headline(img, t, over, head, color="white", y=400, reveal=0.35):
    d = ImageDraw.Draw(img)
    if over:
        f = font(34, "bold")
        txt = " ".join(over.upper())  # gesperrt
        a = int(170 * ease(t / 0.3))
        d.text((W / 2, y - 95), txt, font=f, fill=(150, 150, 158, a), anchor="mm")
    if head:
        size = 120
        f = font(size)
        while f.getlength(head.upper()) > W - 140 and size > 60:
            size -= 6
            f = font(size)
        txt = head.upper()
        tw = f.getlength(txt)
        k = ease(t / reveal)
        layer = Image.new("RGBA", (W, 260), (0, 0, 0, 0))
        ImageDraw.Draw(layer).text((W / 2, 130), txt, font=f, fill=col(color) + (255,), anchor="mm")
        cut = int((W - tw) / 2 + tw * k + 40)
        layer = layer.crop((0, 0, max(1, cut), 260))
        if color != "white":
            g = layer.filter(ImageFilter.GaussianBlur(14))
            img.alpha_composite(g, (0, y - 130))
        img.alpha_composite(layer, (0, y - 130))


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
            "stairs": el_stairs}


def render_scene(sc, t, d):
    img = background()
    headline(img, t, sc.get("over"), sc.get("head"), sc.get("color", "white"), sc.get("head_y", 400))
    for e in sc.get("els", []):
        ELEMENTS[e["k"]](img, e, t)
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
