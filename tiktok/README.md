# TikTok-Video-Generator

Macht aus einem kurzen JSON-Skript ein fertiges TikTok-Video (1080×1920, 30 fps, MP4 mit Ton).
Gebaut für kurze Aufmerksamkeitsspannen: Hook in der ersten Sekunde, Schnitte alle 1–3 Sekunden,
Wort-für-Wort-Untertitel (CapCut-Stil), Zoom-Punches, Wackler, Blitze, schwebende Emojis im
Hintergrund, generierter Beat und Soundeffekte (Whoosh, Impact, Tick-Countdown, Ding).

## Video erstellen

```bash
pip install pillow numpy      # außerdem: ffmpeg
python3 tiktok/make_video.py tiktok/scripts/02_gelb_oder_rest.json
python3 tiktok/make_video.py skript.json --no-beat        # nur Soundeffekte, Trend-Sound in TikTok drüberlegen
python3 tiktok/make_video.py skript.json --music song.mp3 # eigene Musik
```

Ergebnis in `tiktok/output/`: `<name>.mp4` + `<name>_caption.txt` (Beschreibung & Hashtags).

## Szenen-Typen

| Typ | Wofür | Felder |
|---|---|---|
| `hook` | Aufhänger in Sekunde 1 | `text`, `emoji`, `sub` |
| `punch` | 1–4 Wörter, knallt mit Blitz & Wackler rein | `text`, `emoji` |
| `captions` | Erklärung als Wort-für-Wort-Untertitel | `text`, `emoji`, `per_word` |
| `quiz` | Frage mit 2 Antworten, Countdown, Auflösung | `emoji`, `item`, `options`, `answer` (0/1), `fact`, `think` |
| `cta` | Ende: Kommentar-/Follow-Aufforderung | `text`, `emoji`, `sub` |

Global: `header` (bleibt oben stehen), `bpm`, `particles` (Hintergrund-Emojis), `theme`
(`bgs`, `accent`, `accent_text`, `glow`, `active`), `caption`.
`*Wort*` bzw. `*mehrere Wörter*` = hervorgehoben. Dauer ist optional (`duration`), sonst automatisch.

## Formate, die gut funktionieren

- **Quiz** („Nur Profis schaffen 5/5"): Leute pausieren und kommentieren ihren Score.
- **Red Flags / Green Flags**: bekanntes Trendformat, schnell und teilbar.
- **„Was wäre, wenn…" / Build in Public**: zeigt SmartWasteAI und sammelt Feedback.
