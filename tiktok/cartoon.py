"""2D-Cartoon-Zeichner: Figuren im Comic-Stil (dicke Konturen, große Augen, Strichbeine) und
gezeichnete Hintergründe. Alles wird mit Pillow gezeichnet, ohne externe Bilder."""
import math
import random

from PIL import Image, ImageDraw, ImageFilter

W, H = 1080, 1920
OUT = (17, 17, 17, 255)  # Konturfarbe
LW = 7                   # Konturbreite


def rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def shade(c, f):
    return tuple(max(0, min(255, int(v * f))) for v in c[:3])


# ---------------------------------------------------------------- Hintergründe

def _floor(d, y0, c1, c2, tile=None):
    d.rectangle([0, y0, W, H], fill=c1)
    if tile:
        vx = W / 2
        for i in range(-12, 13):
            d.line([(vx + i * 40, y0), (vx + i * 260, H)], fill=c2, width=3)
        y, step = y0, 22
        while y < H:
            d.line([(0, y), (W, y)], fill=c2, width=3)
            step *= 1.35
            y += step


def bg_supermarket():
    im = Image.new("RGB", (W, H), rgb("#e8eef3"))
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, W, 260], fill=rgb("#f8fafc"))
    for x in (120, 540, 960):
        d.rounded_rectangle([x - 140, 120, x + 140, 150], radius=12, fill=rgb("#fffbe6"), outline=OUT, width=4)
    rnd = random.Random(4)
    for sx in (-60, 700):
        d.rectangle([sx, 330, sx + 440, 1180], fill=rgb("#cbd5e1"), outline=OUT, width=LW)
        for row in range(5):
            y = 380 + row * 160
            d.rectangle([sx, y + 120, sx + 440, y + 140], fill=rgb("#94a3b8"), outline=OUT, width=4)
            x = sx + 20
            while x < sx + 410:
                w = rnd.randint(40, 70)
                h = rnd.randint(70, 115)
                c = rnd.choice(["#ef4444", "#f59e0b", "#22c55e", "#3b82f6", "#a855f7", "#ec4899", "#14b8a6"])
                d.rounded_rectangle([x, y + 120 - h, x + w, y + 120], radius=6, fill=rgb(c), outline=OUT, width=3)
                x += w + 8
    d.rectangle([440, 300, 700, 1180], fill=rgb("#dbe4ec"))
    d.rounded_rectangle([470, 380, 670, 470], radius=10, fill=rgb("#16a34a"), outline=OUT, width=4)
    d.text((570, 425), "KASSE", fill=(255, 255, 255), anchor="mm", font=_f(46))
    _floor(d, 1180, rgb("#d6dde4"), rgb("#bcc6d0"), tile=True)
    d.rounded_rectangle([-40, 1150, 380, 1350], radius=14, fill=rgb("#475569"), outline=OUT, width=LW)
    d.rectangle([-40, 1150, 380, 1180], fill=rgb("#1f2937"))
    return im


def bg_street_night():
    im = Image.new("RGB", (W, H), rgb("#0b1026"))
    d = ImageDraw.Draw(im)
    for i in range(H // 2):
        c = shade(rgb("#1b2450"), 0.5 + i / H)
        d.line([(0, i), (W, i)], fill=c)
    d.ellipse([760, 170, 900, 310], fill=rgb("#f8fafc"))
    rnd = random.Random(9)
    x = -40
    while x < W:
        w, h = rnd.randint(160, 260), rnd.randint(500, 900)
        top = 1250 - h
        d.rectangle([x, top, x + w, 1250], fill=rgb(rnd.choice(["#1e293b", "#273449", "#1f2a44"])), outline=OUT, width=5)
        for wy in range(top + 40, 1220, 90):
            for wx in range(x + 25, x + w - 40, 60):
                lit = rnd.random() < 0.35
                d.rectangle([wx, wy, wx + 34, wy + 50], fill=rgb("#fde68a") if lit else rgb("#111827"))
        x += w + rnd.randint(10, 40)
    d.rectangle([0, 1250, W, 1330], fill=rgb("#4b5563"), outline=OUT, width=5)
    d.rectangle([0, 1330, W, H], fill=rgb("#1f2937"))
    for i in range(0, W, 220):
        d.rectangle([i + 40, 1600, i + 160, 1620], fill=rgb("#facc15"))
    d.line([(930, 1290), (930, 700)], fill=OUT, width=14)
    d.line([(930, 700), (860, 700)], fill=OUT, width=10)
    d.ellipse([820, 690, 900, 740], fill=rgb("#fef3c7"), outline=OUT, width=4)
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse([700, 700, 1020, 1350], fill=(254, 243, 199, 50))
    im = Image.alpha_composite(im.convert("RGBA"), glow.filter(ImageFilter.GaussianBlur(40))).convert("RGB")
    return im


def bg_living_room():
    im = Image.new("RGB", (W, H), rgb("#3f3a52"))
    d = ImageDraw.Draw(im)
    for x in range(0, W, 90):
        d.line([(x, 0), (x, 1200)], fill=rgb("#38344a"), width=4)
    d.rectangle([600, 300, 960, 760], fill=rgb("#0f172a"), outline=OUT, width=LW)
    d.ellipse([800, 360, 880, 440], fill=rgb("#e2e8f0"))
    d.line([(780, 300), (780, 760)], fill=OUT, width=6)
    d.line([(600, 530), (960, 530)], fill=OUT, width=6)
    d.rectangle([60, 180, 330, 420], fill=rgb("#78350f"), outline=OUT, width=LW)
    d.rectangle([90, 210, 300, 390], fill=rgb("#a7c4a0"))
    d.rectangle([0, 1200, W, H], fill=rgb("#57423a"))
    for y in range(1240, H, 70):
        d.line([(0, y), (W, y)], fill=rgb("#4a3730"), width=4)
    d.rounded_rectangle([40, 950, 1040, 1260], radius=50, fill=rgb("#7c2d12"), outline=OUT, width=LW)
    d.rounded_rectangle([20, 900, 140, 1270], radius=40, fill=rgb("#6b2510"), outline=OUT, width=LW)
    d.rounded_rectangle([940, 900, 1060, 1270], radius=40, fill=rgb("#6b2510"), outline=OUT, width=LW)
    return im


def bg_forest_night():
    im = Image.new("RGB", (W, H), rgb("#07130d"))
    d = ImageDraw.Draw(im)
    for i in range(1300):
        d.line([(0, i), (W, i)], fill=shade(rgb("#12301f"), 0.4 + i / 2200))
    d.ellipse([140, 160, 300, 320], fill=rgb("#f1f5f9"))
    rnd = random.Random(2)
    for layer, (col, base) in enumerate([("#0d2418", 1150), ("#11301f", 1250), ("#163d28", 1350)]):
        for _ in range(7):
            x = rnd.randint(-80, W + 80)
            h = rnd.randint(500, 800)
            d.rectangle([x - 22, base - 120, x + 22, base + 40], fill=rgb("#3b2a1a"), outline=OUT, width=4)
            for k in range(3):
                yy = base - 120 - k * h / 4
                d.polygon([(x, yy - h / 2.6), (x - 150 + k * 25, yy), (x + 150 - k * 25, yy)], fill=rgb(col),
                          outline=OUT)
    d.rectangle([0, 1350, W, H], fill=rgb("#14261b"))
    fog = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(fog).rectangle([0, 1150, W, 1500], fill=(200, 220, 210, 45))
    return Image.alpha_composite(im.convert("RGBA"), fog.filter(ImageFilter.GaussianBlur(50))).convert("RGB")


def bg_cabin():
    im = Image.new("RGB", (W, H), rgb("#7c4a26"))
    d = ImageDraw.Draw(im)
    for y in range(0, 1200, 80):
        d.rectangle([0, y, W, y + 80], fill=rgb("#8a5530") if (y // 80) % 2 else rgb("#7c4a26"), outline=OUT, width=3)
    d.rectangle([700, 420, 1000, 1210], fill=rgb("#5a3418"), outline=OUT, width=LW)
    d.ellipse([940, 800, 970, 830], fill=rgb("#facc15"), outline=OUT, width=3)
    d.rectangle([0, 1200, W, H], fill=rgb("#5b3a1e"))
    d.rectangle([60, 960, 520, 1000], fill=rgb("#4a2c14"), outline=OUT, width=LW)
    d.line([(100, 1000), (100, 1220)], fill=OUT, width=12)
    d.line([(480, 1000), (480, 1220)], fill=OUT, width=12)
    d.rounded_rectangle([170, 840, 410, 960], radius=14, fill=rgb("#b45309"), outline=OUT, width=LW)
    d.ellipse([200, 860, 280, 940], fill=rgb("#1f2937"), outline=OUT, width=4)
    for i in range(4):
        d.line([(300, 870 + i * 20), (390, 870 + i * 20)], fill=OUT, width=5)
    d.line([(380, 840), (420, 760)], fill=OUT, width=5)
    return im


def bg_lab():
    im = Image.new("RGB", (W, H), rgb("#dff3f1"))
    d = ImageDraw.Draw(im)
    for x in range(0, W, 180):
        d.rectangle([x, 0, x + 180, 1180], outline=rgb("#c3e4e0"), width=4)
    for i, x in enumerate((90, 300, 780, 990)):
        d.rounded_rectangle([x - 70, 320, x + 70, 1100], radius=60, fill=rgb("#e0f2fe"), outline=OUT, width=LW)
        d.rounded_rectangle([x - 58, 620 + i * 40, x + 58, 1088], radius=50, fill=rgb("#4ade80"))
        for b in range(5):
            by = 700 + b * 80 + i * 10
            d.ellipse([x - 10 + (b % 2) * 20, by, x + 10 + (b % 2) * 20, by + 20], outline=rgb("#bbf7d0"), width=3)
    d.rounded_rectangle([400, 260, 680, 460], radius=10, fill=rgb("#0f172a"), outline=OUT, width=LW)
    pts = [(420 + i * 13, 360 + 40 * math.sin(i * 0.9)) for i in range(20)]
    d.line(pts, fill=rgb("#22c55e"), width=5)
    _floor(d, 1180, rgb("#cfe7e3"), rgb("#b5d6d1"), tile=True)
    return im


def bg_kitchen():
    im = Image.new("RGB", (W, H), rgb("#fde7c8"))
    d = ImageDraw.Draw(im)
    for y in range(560, 960, 60):
        for x in range(0, W, 60):
            d.rectangle([x, y, x + 60, y + 60], fill=rgb("#f8fafc"), outline=rgb("#cbd5e1"), width=2)
    d.rectangle([0, 280, W, 560], fill=rgb("#fde7c8"))
    for x in (40, 380, 720):
        d.rectangle([x, 300, x + 320, 520], fill=rgb("#0f766e"), outline=OUT, width=LW)
        d.line([(x + 160, 300), (x + 160, 520)], fill=OUT, width=5)
    d.rectangle([0, 960, W, 1240], fill=rgb("#115e59"), outline=OUT, width=LW)
    d.rectangle([0, 940, W, 980], fill=rgb("#e2e8f0"), outline=OUT, width=LW)
    d.rectangle([0, 1240, W, H], fill=rgb("#d6c2a8"))
    for y in range(1270, H, 80):
        d.line([(0, y), (W, y)], fill=rgb("#c4ae92"), width=4)
    d.rounded_rectangle([760, 120, 900, 260], radius=70, fill=rgb("#ffffff"), outline=OUT, width=LW)
    d.line([(830, 190), (830, 140)], fill=OUT, width=6)
    d.line([(830, 190), (865, 205)], fill=OUT, width=6)
    return im


def bg_bedroom():
    im = Image.new("RGB", (W, H), rgb("#1e1b4b"))
    d = ImageDraw.Draw(im)
    d.rectangle([380, 220, 700, 640], fill=rgb("#0b1026"), outline=OUT, width=LW)
    d.ellipse([560, 270, 640, 350], fill=rgb("#e2e8f0"))
    d.line([(540, 220), (540, 640)], fill=OUT, width=6)
    d.rectangle([0, 1180, W, H], fill=rgb("#312e81"))
    d.rounded_rectangle([60, 860, 1020, 1240], radius=40, fill=rgb("#4338ca"), outline=OUT, width=LW)
    d.rounded_rectangle([40, 700, 1040, 900], radius=40, fill=rgb("#3730a3"), outline=OUT, width=LW)
    d.rounded_rectangle([120, 880, 420, 990], radius=40, fill=rgb("#e0e7ff"), outline=OUT, width=LW)
    d.rounded_rectangle([660, 880, 960, 990], radius=40, fill=rgb("#e0e7ff"), outline=OUT, width=LW)
    d.rectangle([900, 1000, 1060, 1180], fill=rgb("#78350f"), outline=OUT, width=LW)
    d.polygon([(930, 1000), (1030, 1000), (1000, 900), (960, 900)], fill=rgb("#fde68a"), outline=OUT)
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse([820, 800, 1140, 1120], fill=(253, 230, 138, 60))
    return Image.alpha_composite(im.convert("RGBA"), glow.filter(ImageFilter.GaussianBlur(50))).convert("RGB")


def bg_bar():
    im = Image.new("RGB", (W, H), rgb("#2a1a12"))
    d = ImageDraw.Draw(im)
    for y in range(300, 960, 170):
        d.rectangle([0, y + 120, W, y + 140], fill=rgb("#5b3a1e"), outline=OUT, width=4)
        rnd = random.Random(y)
        x = 30
        while x < W - 40:
            c = rnd.choice(["#16a34a", "#b45309", "#dc2626", "#0ea5e9", "#a16207"])
            h = rnd.randint(70, 110)
            d.rounded_rectangle([x, y + 120 - h, x + 36, y + 120], radius=10, fill=rgb(c), outline=OUT, width=3)
            d.rectangle([x + 12, y + 120 - h - 25, x + 24, y + 120 - h], fill=rgb(c), outline=OUT, width=3)
            x += rnd.randint(50, 80)
    for x in (180, 540, 900):
        d.line([(x, 0), (x, 160)], fill=OUT, width=5)
        d.polygon([(x - 60, 220), (x + 60, 220), (x + 30, 160), (x - 30, 160)], fill=rgb("#f59e0b"), outline=OUT)
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    for x in (180, 540, 900):
        gd.ellipse([x - 200, 180, x + 200, 600], fill=(251, 191, 36, 45))
    im = Image.alpha_composite(im.convert("RGBA"), glow.filter(ImageFilter.GaussianBlur(60))).convert("RGB")
    d = ImageDraw.Draw(im)
    d.rectangle([0, 1180, W, 1260], fill=rgb("#78350f"), outline=OUT, width=LW)
    d.rectangle([0, 1260, W, H], fill=rgb("#3f2a1d"))
    return im


def bg_hotel():
    im = Image.new("RGB", (W, H), rgb("#f3e8d2"))
    d = ImageDraw.Draw(im)
    for x in range(0, W, 270):
        d.rectangle([x + 100, 200, x + 160, 1180], fill=rgb("#e7d5b5"), outline=OUT, width=5)
    d.rounded_rectangle([300, 270, 780, 370], radius=12, fill=rgb("#7c2d12"), outline=OUT, width=LW)
    d.text((540, 320), "HOTEL ASTORIA", fill=rgb("#fde68a"), anchor="mm", font=_f(44))

    d.rectangle([0, 1180, W, H], fill=rgb("#7f1d1d"))
    d.rectangle([340, 1180, 740, H], fill=rgb("#991b1b"))
    d.line([(340, 1180), (340, H)], fill=rgb("#fbbf24"), width=8)
    d.line([(740, 1180), (740, H)], fill=rgb("#fbbf24"), width=8)
    d.rounded_rectangle([700, 980, 1100, 1220], radius=14, fill=rgb("#78350f"), outline=OUT, width=LW)
    d.text((900, 1100), "REZEPTION", fill=rgb("#fde68a"), anchor="mm", font=_f(40))
    return im


def bg_car_night():
    im = bg_street_night()
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, W, 140], fill=rgb("#111827"))
    d.polygon([(0, 140), (120, 140), (0, 900)], fill=rgb("#111827"))
    d.polygon([(W, 140), (W - 120, 140), (W, 900)], fill=rgb("#111827"))
    d.rectangle([0, 1250, W, H], fill=rgb("#1f2937"))
    d.rounded_rectangle([-40, 1180, W + 40, 1340], radius=60, fill=rgb("#374151"), outline=OUT, width=LW)
    d.ellipse([60, 1260, 360, 1560], outline=OUT, width=26)
    d.ellipse([170, 1370, 250, 1450], fill=OUT)
    d.rounded_rectangle([700, 1210, 900, 1290], radius=10, fill=rgb("#0ea5e9"), outline=OUT, width=4)
    d.line([(0, 140), (W, 140)], fill=OUT, width=10)
    return im


def bg_title():
    im = Image.new("RGB", (W, H), rgb("#111111"))
    return im


BACKGROUNDS = {"supermarket": bg_supermarket, "street_night": bg_street_night, "living_room": bg_living_room,
               "forest_night": bg_forest_night, "cabin": bg_cabin, "lab": bg_lab, "black": bg_title,
               "kitchen": bg_kitchen, "bedroom": bg_bedroom, "bar": bg_bar, "hotel": bg_hotel, "car_night": bg_car_night}
_bg_cache = {}


def background(name):
    if name not in _bg_cache:
        _bg_cache[name] = BACKGROUNDS[name]().convert("RGBA")
    return _bg_cache[name]


_FONT = {}


def _f(size):
    from PIL import ImageFont
    if size not in _FONT:
        for p in ("/usr/share/fonts/opentype/inter/Inter-Black.otf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"):
            try:
                _FONT[size] = ImageFont.truetype(p, size)
                break
            except OSError:
                continue
        else:
            _FONT[size] = ImageFont.load_default(size)
    return _FONT[size]


# ---------------------------------------------------------------- Figuren

DEFAULT_LOOK = {"skin": "#f2c79a", "hair": "short", "hair_color": "#3b2414", "shirt": "#2563eb",
                "jacket": None, "pants": "#1f2937", "shoes": "#ffffff", "hat": None, "glasses": False,
                "zombie": False, "bandage": False}


def _limb(d, pts, width=12):
    d.line(pts, fill=OUT, width=width, joint="curve")
    for p in (pts[0], pts[-1]):
        d.ellipse([p[0] - width / 2, p[1] - width / 2, p[0] + width / 2, p[1] + width / 2], fill=OUT)


def draw_character(layer, look, cx, ground, scale, t, mouth=0.0, expr="neutral", pose="idle", look_dir=0.0,
                   talking=False, seed=0):
    """Zeichnet eine Comic-Figur. ground = y der Fußsohlen, scale 1 ≈ 1350 px hoch."""
    L = dict(DEFAULT_LOOK, **look)
    d = ImageDraw.Draw(layer)
    s = scale
    breathe = math.sin(t * 2.2 + seed) * 6 * s
    skin = rgb(L["skin"])
    if L["zombie"]:
        skin = rgb(L.get("skin", "#8fbc6a"))

    def P(x, y):
        return (cx + x * s, ground - y * s)

    hip_y, sh_y = 640, 1000 + breathe / s
    head_y = 1160 + breathe / s
    # --- Beine (Strichbeine) + Schuhe
    run = pose == "run"
    for side in (-1, 1):
        sw = math.sin(t * 12 + (0 if side < 0 else math.pi)) * 70 if run else 0
        _limb(d, [P(side * 45, hip_y - 60), P(side * 50 + sw * 0.5, 330), P(side * 60 + sw, 50)], int(15 * s))
        fx, fy = P(side * 60 + sw + side * 25, 30)
        d.ellipse([fx - 80 * s, fy - 38 * s, fx + 80 * s, fy + 38 * s], fill=rgb(L["shoes"]), outline=OUT, width=LW)
    # --- Hose (kurz) und Oberkörper
    x0, y0 = P(-105, hip_y + 20)
    x1, y1 = P(105, hip_y - 130)
    d.rounded_rectangle([x0, y0, x1, y1], radius=int(30 * s), fill=rgb(L["pants"]), outline=OUT, width=LW)
    tx0, ty0 = P(-110, sh_y)
    tx1, ty1 = P(110, hip_y)
    shirt = rgb(L["shirt"])
    d.rounded_rectangle([tx0, ty0, tx1, ty1], radius=int(55 * s), fill=shirt, outline=OUT, width=LW)
    if L["zombie"]:
        jag = [P(-110 + i * 22, hip_y + (25 if i % 2 else 0)) for i in range(11)]
        d.polygon([P(-110, hip_y + 60)] + jag + [P(110, hip_y + 60)], fill=shirt)
        d.line([P(-40, 900), P(-10, 830), P(-50, 760)], fill=OUT, width=5)
        d.line([P(40, 780), P(70, 720)], fill=OUT, width=5)
    if L["jacket"]:
        jc = rgb(L["jacket"])
        d.rounded_rectangle([tx0, ty0, P(-25, 0)[0], ty1], radius=int(50 * s), fill=jc, outline=OUT, width=LW)
        d.rounded_rectangle([P(25, 0)[0], ty0, tx1, ty1], radius=int(50 * s), fill=jc, outline=OUT, width=LW)
    # --- Arme
    talk_wave = math.sin(t * 7 + seed) if talking else 0
    for side in (-1, 1):
        shx, shy = side * 100, sh_y - 30
        if pose == "zombie":
            elbow, hand = (side * 210, shy + 10 + math.sin(t * 3 + side) * 15), (side * 300, shy + 30 + math.sin(t * 3 + side) * 20)
        elif pose == "shock":
            elbow, hand = (side * 200, shy + 40), (side * 120, head_y + 40)
        elif pose == "phone" and side == 1:
            elbow, hand = (side * 190, shy - 60), (side * 125, head_y - 10)
        elif pose == "run":
            sw = math.sin(t * 12 + (math.pi if side < 0 else 0)) * 60
            elbow, hand = (side * 160, shy - 120 + sw), (side * 170 + sw, shy - 260 + sw)
        elif pose == "hips":
            elbow, hand = (side * 210, shy - 170), (side * 115, hip_y + 40)
        elif talking and side == 1:
            elbow, hand = (side * 200, shy - 150), (side * 230, shy - 40 + talk_wave * 50)
        elif pose == "sad":
            elbow, hand = (side * 130, shy - 200), (side * 60, hip_y - 20)
        else:
            elbow, hand = (side * 150, shy - 190), (side * 165, hip_y - 60)
        _limb(d, [P(shx, shy), P(*elbow), P(*hand)], int(14 * s))
        hx, hy = P(*hand)
        d.ellipse([hx - 24 * s, hy - 24 * s, hx + 24 * s, hy + 24 * s], fill=OUT)
        if L["bandage"] and side == -1:
            bx, by = P((shx + elbow[0]) / 2, (shy + elbow[1]) / 2)
            d.rounded_rectangle([bx - 26 * s, by - 18 * s, bx + 26 * s, by + 18 * s], radius=8, fill=(250, 250, 250),
                                outline=OUT, width=4)
            d.ellipse([bx - 8 * s, by - 6 * s, bx + 8 * s, by + 6 * s], fill=(220, 38, 38))
        if pose == "phone" and side == 1:
            d.rounded_rectangle([hx - 20 * s, hy - 55 * s, hx + 20 * s, hy + 20 * s], radius=8, fill=(30, 30, 30),
                                outline=OUT, width=3)
    # --- Hals + Kopf
    d.rectangle([P(-22, sh_y + 60)[0], P(0, sh_y + 60)[1], P(22, 0)[0], P(0, sh_y - 10)[1]], fill=skin, outline=OUT,
                width=5)
    hx, hy = P(0, head_y)
    R = 135 * s
    hair_c = rgb(L["hair_color"])
    if L["hair"] == "long":
        for side in (-1, 1):
            x_in, x_out = hx + side * R * 0.55, hx + side * R * 1.12
            d.rounded_rectangle([min(x_in, x_out), hy - R * 0.6, max(x_in, x_out), hy + R * 1.45], radius=int(R * 0.3),
                                fill=hair_c, outline=OUT, width=LW)
    if L["hair"] == "pigtails":
        d.rounded_rectangle([hx - R * 1.08, hy - R * 0.9, hx + R * 1.08, hy + R * 1.25], radius=int(R),
                            fill=hair_c, outline=OUT, width=LW)
        if L["hair"] == "pigtails":
            for side in (-1, 1):
                d.ellipse([hx + side * R * 1.1 - 50 * s, hy - 10 * s, hx + side * R * 1.1 + 50 * s, hy + 150 * s],
                          fill=hair_c, outline=OUT, width=LW)
    if L["hair"] == "bun":
        d.ellipse([hx - 60 * s, hy - R - 95 * s, hx + 60 * s, hy - R + 20 * s], fill=hair_c, outline=OUT, width=LW)
    d.ellipse([hx - R, hy - R * 1.05, hx + R, hy + R * 0.95], fill=skin, outline=OUT, width=LW)
    # Haare / Hut oben drauf
    if L["hair"] == "short":
        d.chord([hx - R * 1.02, hy - R * 1.12, hx + R * 1.02, hy + R * 0.4], 180, 360, fill=hair_c, outline=OUT,
                width=LW)
        for i in range(5):
            x = hx - R * 0.8 + i * R * 0.4
            d.polygon([(x - 25 * s, hy - R * 0.36), (x + 25 * s, hy - R * 0.36), (x + 5 * s, hy - R * 0.12)],
                      fill=hair_c)
    elif L["hair"] == "cap":
        d.chord([hx - R * 1.08, hy - R * 1.2, hx + R * 1.08, hy + R * 0.25], 175, 365, fill=hair_c, outline=OUT,
                width=LW)
        d.pieslice([hx - R * 1.1, hy - R * 0.5, hx + R * 0.2, hy + R * 0.1], 180, 270, fill=hair_c, outline=OUT,
                   width=LW)
    elif L["hair"] in ("long", "pigtails", "bun"):
        d.chord([hx - R * 1.02, hy - R * 1.1, hx + R * 1.02, hy + R * 0.2], 180, 360, fill=hair_c, outline=OUT,
                width=LW)
    elif L["hair"] == "messy":
        for i in range(9):
            a = math.pi + i * math.pi / 8
            x, y = hx + math.cos(a) * R * 0.95, hy - R * 0.05 + math.sin(a) * R * 1.0
            d.ellipse([x - 40 * s, y - 40 * s, x + 40 * s, y + 40 * s], fill=hair_c, outline=OUT, width=4)
    if L["hat"] == "cowboy":
        d.ellipse([hx - R * 1.6, hy - R * 0.85, hx + R * 1.6, hy - R * 0.45], fill=rgb("#8b5a2b"), outline=OUT,
                  width=LW)
        d.rounded_rectangle([hx - R * 0.85, hy - R * 1.6, hx + R * 0.85, hy - R * 0.6], radius=int(40 * s),
                            fill=rgb("#8b5a2b"), outline=OUT, width=LW)
    # --- Gesicht
    blink = (t * 1.0 + seed * 0.37) % 3.4 < 0.12
    eye_y = hy - R * 0.05
    ew, eh = R * 0.36, R * 0.42
    lid = {"neutral": 0.42, "tired": 0.55, "angry": 0.5, "shock": 0.0, "sad": 0.35, "smirk": 0.5, "happy": 0.3,
           "zombie": 0.2}.get(expr, 0.42)
    if blink:
        lid = 1.0
    for side in (-1, 1):
        ex = hx + side * R * 0.38
        d.ellipse([ex - ew, eye_y - eh, ex + ew, eye_y + eh], fill=(255, 255, 255), outline=OUT, width=6)
        pr = (ew * 0.32) if expr != "shock" else ew * 0.22
        px = ex + look_dir * ew * 0.45
        py = eye_y + eh * 0.15
        pc = (200, 20, 20) if L["zombie"] or L.get("red_eyes") else (17, 17, 17)
        if lid < 1:
            d.ellipse([px - pr, py - pr, px + pr, py + pr], fill=pc)
        if lid > 0:
            k = max(-0.999, min(0.999, 2 * lid - 1))
            a1 = math.degrees(math.pi - math.asin(k))
            a2 = math.degrees(2 * math.pi + math.asin(k))
            d.chord([ex - ew, eye_y - eh, ex + ew, eye_y + eh], a1, a2, fill=skin)
            ly = eye_y + eh * k
            half = ew * math.sqrt(max(0, 1 - k * k))
            d.line([(ex - half, ly), (ex + half, ly)], fill=OUT, width=7)
            d.ellipse([ex - ew, eye_y - eh, ex + ew, eye_y + eh], outline=OUT, width=6)
        brow_y = eye_y - eh - 18 * s
        if expr == "angry":
            d.line([(ex - side * ew, brow_y - 10 * s), (ex + side * ew * 0.2, brow_y + 18 * s)], fill=OUT, width=10)
        elif expr == "sad":
            d.line([(ex - side * ew * 0.9, brow_y + 10 * s), (ex + side * ew * 0.3, brow_y - 14 * s)], fill=OUT, width=9)
        elif expr == "shock":
            d.arc([ex - ew, brow_y - 40 * s, ex + ew, brow_y + 10 * s], 200, 340, fill=OUT, width=8)
    if L["glasses"]:
        for side in (-1, 1):
            ex = hx + side * R * 0.38
            d.ellipse([ex - ew - 8, eye_y - eh * 0.8, ex + ew + 8, eye_y + eh * 0.8], outline=OUT, width=7)
        d.line([(hx - R * 0.05, eye_y), (hx + R * 0.05, eye_y)], fill=OUT, width=7)
    # Mund
    my = hy + R * 0.55
    mw = R * 0.32
    if mouth > 0.08 or expr in ("shock", "zombie"):
        op = max(mouth, 0.55 if expr in ("shock", "zombie") else 0)
        mh = R * 0.08 + R * 0.32 * min(1, op)
        d.ellipse([hx - mw * (0.8 + 0.2 * op), my - mh / 2, hx + mw * (0.8 + 0.2 * op), my + mh / 2],
                  fill=(120, 20, 30), outline=OUT, width=6)
        d.chord([hx - mw * 0.5, my, hx + mw * 0.5, my + mh / 2 - 2], 0, 180, fill=(230, 90, 100))
        if expr == "zombie":
            for i in range(3):
                x = hx - mw * 0.5 + i * mw * 0.5
                d.polygon([(x - 10, my - mh / 2 + 2), (x + 10, my - mh / 2 + 2), (x, my - mh / 2 + 22)],
                          fill=(240, 240, 220))
    elif expr in ("smirk", "happy"):
        d.arc([hx - mw, my - R * 0.25, hx + mw, my + R * 0.12], 20, 160 if expr == "happy" else 110, fill=OUT, width=7)
    elif expr == "sad":
        d.arc([hx - mw * 0.8, my, hx + mw * 0.8, my + R * 0.3], 200, 340, fill=OUT, width=7)
    else:
        d.line([(hx - mw * 0.7, my), (hx + mw * 0.7, my)], fill=OUT, width=7)


def car_foreground(layer):
    """Armaturenbrett + Lenkrad vor der Figur (Auto-Szenen)."""
    d = ImageDraw.Draw(layer)
    d.rectangle([0, 1240, W, H], fill=rgb("#1f2937"))
    d.rounded_rectangle([-40, 1150, W + 40, 1330], radius=60, fill=rgb("#374151"), outline=OUT, width=LW)
    d.ellipse([200, 1050, 620, 1470], outline=OUT, width=30)
    d.ellipse([370, 1220, 450, 1300], fill=OUT)
    d.line([(410, 1260), (230, 1200)], fill=OUT, width=18)
    d.line([(410, 1260), (590, 1200)], fill=OUT, width=18)
    d.rounded_rectangle([760, 1190, 960, 1270], radius=10, fill=rgb("#0ea5e9"), outline=OUT, width=4)
