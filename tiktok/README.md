# TikTok-Video-Generator

Erstellt fertige TikTok-Videos (1080×1920, 30 fps, MP4) aus einem einfachen Text-Skript.

## Ein Video erstellen

```bash
pip install pillow          # einmalig; außerdem wird ffmpeg benötigt
python3 tiktok/make_video.py tiktok/scripts/01_falsche_tonne.json
# optional mit Musik:
python3 tiktok/make_video.py tiktok/scripts/01_falsche_tonne.json --music song.mp3
```

Ergebnis: `tiktok/output/<name>.mp4` + `<name>_caption.txt` (Beschreibung & Hashtags zum Kopieren).

Tipp: Trend-Sounds am besten direkt in der TikTok-App hinzufügen, das bringt mehr Reichweite.

## Skript-Format

```json
{
  "handle": "@deinname",
  "theme": { "bg": ["#14532d", "#052e16"], "accent": "#4ade80", "text": "#ffffff" },
  "caption": "Beschreibung #hashtags",
  "scenes": [
    { "type": "hook", "text": "Großer *Aufhänger*", "sub": "Untertitel", "duration": 3.5 },
    { "type": "text", "label": "Fakt", "headline": "Überschrift", "body": "Fließtext …", "duration": 5 },
    { "type": "list", "headline": "3 Tipps", "items": ["Tipp eins", "Tipp *zwei*"], "duration": 6 },
    { "type": "cta", "text": "Folge für mehr!", "button": "Folgen", "duration": 3 }
  ]
}
```

- `*Wort*` wird in der Akzentfarbe hervorgehoben.
- Die Texte bleiben in der sicheren Zone, damit TikToks Buttons und Beschreibung nichts verdecken.
- Emojis werden im Video nicht dargestellt. Verwende sie nur in der `caption`.
