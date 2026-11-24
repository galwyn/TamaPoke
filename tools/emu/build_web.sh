#!/bin/bash
# Builds the emulator for the browser (WebAssembly) into tools/emu/web/.
#   bash tools/emu/build_web.sh && python3 -m http.server -d tools/emu/web 8765
# Needs Emscripten (brew install emscripten). Sprites in tools/sdcard/mons are
# bundled into the page.
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
cd "$HERE"
python3 genproto.py "$ROOT/TamaPoke.ino"
{ echo '#include "proto.h"'; cat "$ROOT/TamaPoke.ino"; } > sketch.cpp
mkdir -p web
PRELOAD=()
[ -d "$ROOT/tools/sdcard/mons" ] && PRELOAD=(--preload-file "$ROOT/tools/sdcard/mons@/mons")
em++ -std=c++17 -O2 -w -I. -I"$ROOT" -DSPRITE_DIR='"/mons"' \
  -sUSE_SDL=2 -sASYNCIFY -sALLOW_MEMORY_GROWTH=1 \
  -sEXPORTED_RUNTIME_METHODS=ccall -sINVOKE_RUN=1 \
  -o web/tamapoke.js \
  sketch.cpp wavout.cpp "$ROOT/gbsynth.cpp" "$ROOT/pet.cpp" "$ROOT/i18n.cpp" "$ROOT/party.cpp" "$ROOT/battle.cpp" "$ROOT/link.cpp" "$ROOT/save.cpp" \
  host_impl.cpp font.cpp clock.cpp main_sdl.cpp \
  "${PRELOAD[@]}"
cp index.html web/index.html
echo "built: $HERE/web"
