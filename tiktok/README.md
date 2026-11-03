# TikTok-Video-Generator

Macht aus einem kurzen JSON-Skript ein fertiges TikTok-Video (1080×1920, 30 fps, MP4 mit Ton).
Gebaut für kurze Aufmerksamkeitsspannen: Hook in der ersten Sekunde, Schnitte alle 1–3 Sekunden,
Wort-für-Wort-Untertitel (CapCut-Stil), Zoom-Punches, Wackler, Blitze, schwebende Emojis im
Hintergrund, generierter Beat und Soundeffekte (Whoosh, Impact, Tick-Countdown, Ding).

## Video erstellen

```bash
pip install pillow numpy piper-tts   # außerdem: ffmpeg
tiktok/get_voices.sh                 # einmalig: deutsche Stimmen laden (Thorsten, Kerstin, Ramona)
python3 tiktok/make_video.py tiktok/scripts/02_gelb_oder_rest.json
python3 tiktok/make_video.py skript.json --no-beat        # nur Soundeffekte, Trend-Sound in TikTok drüberlegen
python3 tiktok/make_video.py skript.json --music song.mp3 # eigene Musik
python3 tiktok/make_video.py skript.json --voice kerstin   # andere Stimme
python3 tiktok/make_video.py skript.json --no-voice        # ohne Vorlesen
```

## Vorlese-Stimme

Alle Texte auf dem Bildschirm werden automatisch vorgelesen (Piper, läuft offline). Die Szenen werden
so lang, wie die Stimme braucht; die Untertitel laufen im Takt der Sprache mit, und die Musik wird beim
Sprechen automatisch leiser. Im Skript einstellbar:

- `"voice"`: `thorsten-high` (Standard, am klarsten), `thorsten_emotional:amused` (fröhlich, etwas undeutlicher), `thorsten_emotional:surprised`, `kerstin`, `ramona` oder `none`
- `"speed": 0.92` (kleiner = schneller), `"pitch": 1` (Stimme in Halbtönen höher)
- `"pronounce": {"Wort": "Aussprache"}` für Wörter, die falsch klingen
- pro Szene `"say"` / `"say_reveal"`, wenn etwas anderes gesprochen werden soll als auf dem Bildschirm steht

### Saubere deutsche Aussprache

- Zahlen werden ausgeschrieben (2024 → „zweitausendvierundzwanzig“), `%` → „Prozent“, `5/5` → „fünf von fünf“.
- Anglizismen werden deutsch korrekt gesprochen („recyceln“ → ri-SAI-keln, „Kassenbon“ → Kassenbong).
- Englische Begriffe in den Skripten möglichst vermeiden (lieber „E-Zigarette“ statt „Vape“).
- **Aussprache prüfen:** `tiktok/check_aussprache.py skript.json` lässt alle Sätze von einer
  Spracherkennung (Whisper) anhören und markiert Sätze, die nicht sauber verstanden werden.

Ergebnis in `tiktok/output/`: `<name>.mp4` + `<name>_caption.txt` (Beschreibung & Hashtags).

## Szenen-Typen

| Typ | Wofür | Felder |
|---|---|---|
| `hook` | Aufhänger in Sekunde 1 | `text`, `emoji`, `sub` |
| `punch` | 1–4 Wörter, knallt mit Blitz & Wackler rein | `text`, `emoji` |
| `captions` | Erklärung als Wort-für-Wort-Untertitel | `text`, `emoji`, `per_word` |
| `quiz` | Frage mit 2 Antworten, Countdown, Auflösung | `emoji`, `item`, `options`, `answer` (0/1), `fact`, `think` |
| `scan` | KI-Scanner: Ladebalken, dann Ergebnis-Tonne | `emoji`, `item`, `result`, `bin` (gelb/rest/papier/bio/glas/pfand), `confidence`, `fact` |
| `fact` | Fakten-Karte mit Zähler (FAKT 3/10), Schlagzeile + Erklärung | `emoji`, `text`, `sub` |
| `cta` | Ende: Kommentar-/Follow-Aufforderung | `text`, `emoji`, `sub` |

Global: `header` (bleibt oben stehen), `bpm`, `particles` (Hintergrund-Emojis), `theme`
(`bgs`, `accent`, `accent_text`, `glow`, `active`), `caption`.
`*Wort*` bzw. `*mehrere Wörter*` = hervorgehoben. Dauer ist optional (`duration`), sonst automatisch.

## Formate, die gut funktionieren

- **Quiz** („Nur Profis schaffen 5/5"): Leute pausieren und kommentieren ihren Score.
- **Red Flags / Green Flags**: bekanntes Trendformat, schnell und teilbar.
- **„Was wäre, wenn…" / Build in Public**: zeigt SmartWasteAI und sammelt Feedback.
