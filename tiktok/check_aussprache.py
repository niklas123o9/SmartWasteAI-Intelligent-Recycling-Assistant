#!/usr/bin/env python3
"""Aussprache-Check: liest alle Texte eines Skripts mit der eingestellten Stimme vor, lässt sie von
Whisper (Spracherkennung) transkribieren und markiert Sätze, die nicht sauber verstanden werden.

    pip install sherpa-onnx
    tiktok/check_aussprache.py --download          # einmalig Whisper-Modell laden (~380 MB)
    tiktok/check_aussprache.py tiktok/scripts/07_10_fakten.json
"""
import difflib
import json
import os
import re
import subprocess
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import make_video as mv  # noqa: E402

ASR = os.path.join(HERE, "asr", "sherpa-onnx-whisper-small")
URL = "https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/sherpa-onnx-whisper-small.tar.bz2"


def download():
    os.makedirs(os.path.dirname(ASR), exist_ok=True)
    subprocess.run(f"curl -sL {URL} | tar xj -C {os.path.dirname(ASR)} "
                   "--wildcards '*int8.onnx' '*tokens.txt'", shell=True, check=True)


def norm(s):
    s = re.sub(r"\d+", lambda m: mv.zahl(int(m.group(0))), s)
    s = s.lower().replace("%", " prozent").replace("-", " ")
    s = s.replace("rissaik", "recyc").replace("sent", "cent").replace("kassenbong", "kassenbon").replace("kwiss", "quiz")
    return " ".join(re.sub(r"[^\wäöüß ]", " ", s).split())


def check(path, rec):
    sc = json.load(open(path, encoding="utf-8"))
    name, spk = sc.get("voice", "thorsten-high"), None
    if ":" in name:
        name, spk = name.split(":", 1)
    cands = [f"de_DE-{name}-high.onnx", f"de_DE-{name}-medium.onnx", f"de_DE-{name}.onnx", f"de-{name}-low.onnx"]
    vp = next(os.path.join(HERE, "voices", c) for c in cands if os.path.exists(os.path.join(HERE, "voices", c)))
    v = mv.Voice(vp, sc.get("speed", 0.92), spk)
    said, orig = [], v.say
    v.say = lambda t: said.append((t, orig(t))) or said[-1][1]
    mv.plan_voice(sc["scenes"], v, sc.get("pronounce"))
    bad = 0
    for text, a in said:
        if len(a) < 100:
            continue
        st = rec.create_stream()
        st.accept_waveform(v.sr, np.concatenate([a, np.zeros(v.sr // 2, np.float32)]))
        rec.decode_stream(st)
        hyp = st.result.text.strip()
        r = difflib.SequenceMatcher(None, norm(text), norm(hyp)).ratio()
        bad += r < 0.85
        print(f"{'!!' if r < 0.85 else 'ok'} {r:.2f} | {text}\n          gehört: {hyp}")
    print(f"== {os.path.basename(path)}: {bad} von {len(said)} Sätzen auffällig\n")


def main():
    if "--download" in sys.argv:
        download()
        return
    import sherpa_onnx
    rec = sherpa_onnx.OfflineRecognizer.from_whisper(
        encoder=os.path.join(ASR, "small-encoder.int8.onnx"), decoder=os.path.join(ASR, "small-decoder.int8.onnx"),
        tokens=os.path.join(ASR, "small-tokens.txt"), language="de", task="transcribe", num_threads=4)
    for p in sys.argv[1:]:
        check(p, rec)


if __name__ == "__main__":
    main()
