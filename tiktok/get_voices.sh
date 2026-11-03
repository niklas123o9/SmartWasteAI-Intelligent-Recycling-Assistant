#!/usr/bin/env bash
# Lädt die deutschen Piper-Stimmen (offline, kostenlos) nach tiktok/voices/.
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p voices
# klar + fröhlich (Thorsten High / Thorsten Emotional)
for n in de_DE-thorsten-high de_DE-thorsten_emotional-medium; do
  [ -f "voices/$n.onnx" ] && continue
  curl -sL "https://github.com/k2-fsa/sherpa-onnx/releases/download/tts-models/vits-piper-$n.tar.bz2" \
    | tar xj -C voices --strip-components=1 "vits-piper-$n/$n.onnx" "vits-piper-$n/$n.onnx.json"
done
# ältere, einfache Stimmen
for n in thorsten kerstin ramona; do
  [ -f "voices/de-$n-low.onnx" ] && continue
  curl -sL "https://github.com/rhasspy/piper/releases/download/v0.0.2/voice-de-$n-low.tar.gz" | tar xz -C voices
done
rm -f voices/MODEL_CARD
ls voices
