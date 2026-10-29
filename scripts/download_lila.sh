#!/usr/bin/env bash
# Baja los clips CDLA de Seattle(ish) Camera Traps usados en el demo.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BASE="https://lilawildlife.blob.core.windows.net/lila-wildlife/seattleish-camera-traps"
mkdir -p "$ROOT/data/lila/coyote" "$ROOT/data/lila/person"

get() {
  local rel="$1" dest="$2"
  echo "→ $dest"
  curl -sL --fail --max-time 180 -o "$dest" "$BASE/$rel"
  ls -lah "$dest"
}

get "converted_camera_trap_videos/2021.03.21/location-03/coyote/DSCF0104.MP4" "$ROOT/data/lila/coyote/DSCF0104.MP4"
get "converted_camera_trap_videos/2021.03.21/location-03/coyote/DSCF0112.MP4" "$ROOT/data/lila/coyote/DSCF0112.MP4"
get "converted_camera_trap_videos/2021.06.06/location-03/coyote/DSCF0840.MP4" "$ROOT/data/lila/coyote/DSCF0840.MP4"
get "converted_camera_trap_videos/2021.03.21/location-03/dan/DSCF0004.MP4" "$ROOT/data/lila/person/DSCF0004.MP4"
echo "Listo. Licencia CDLA-Permissive — ver DATA.md"
