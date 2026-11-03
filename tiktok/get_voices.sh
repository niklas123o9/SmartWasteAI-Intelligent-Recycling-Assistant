#!/usr/bin/env bash
# Lädt die deutschen Piper-Stimmen (offline, kostenlos) nach tiktok/voices/.
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p voices
for n in thorsten kerstin ramona; do
  [ -f "voices/de-$n-low.onnx" ] && continue
  curl -sL "https://github.com/rhasspy/piper/releases/download/v0.0.2/voice-de-$n-low.tar.gz" | tar xz -C voices
done
rm -f voices/MODEL_CARD
ls voices
