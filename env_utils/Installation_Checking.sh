#!/usr/bin/env bash
set -e

section(){ printf "\n== %s ==\n" "$1"; }
found(){ printf "FOUND: %s\n" "$1"; }
notfound(){ printf "NOT FOUND: %s\n" "$1"; }

section "CAT12 (MATLAB/SPM toolbox)"
if command -v matlab >/dev/null 2>&1 || command -v octave >/dev/null 2>&1; then
  : # just informational; CAT12 itself is usually not a standalone command
fi

# Look for a cat12 directory in common SPM/toolbox locations + user home
CAT_HITS="$(find "$HOME" /usr/local /opt 2>/dev/null -maxdepth 5 -type d -iname "cat12" | head -n 20 || true)"
if [ -n "$CAT_HITS" ]; then
  found "CAT12 directory candidates:"
  printf "%s\n" "$CAT_HITS"
else
  notfound "CAT12 folder named \"cat12\" in common locations (HOME,/usr/local,/opt)"
fi

section "SAMSEG (FreeSurfer)"
if command -v run_samseg >/dev/null 2>&1; then
  found "run_samseg: $(command -v run_samseg)"
else
  notfound "run_samseg on PATH"
fi

if command -v samseg >/dev/null 2>&1; then
  found "samseg: $(command -v samseg)"
else
  notfound "samseg on PATH"
fi

# If FreeSurfer is configured, show version/home
if [ -n "${FREESURFER_HOME:-}" ]; then
  found "FREESURFER_HOME=$FREESURFER_HOME"
  [ -x "$FREESURFER_HOME/bin/run_samseg" ] && found "$FREESURFER_HOME/bin/run_samseg exists"
fi

section "SynthSeg 2.x / 2.0 (common entry points)"
# Common command names
for c in mri_synthseg synthseg run_synthseg; do
  if command -v "$c" >/dev/null 2>&1; then
    found "$c: $(command -v "$c")"
  else
    notfound "$c on PATH"
  fi
done

# Check if it is installed as a Python package (works if python/pip available)
if command -v python3 >/dev/null 2>&1; then
  python3 - << "PY" 2>/dev/null || true
import importlib.util
pkgs = ["synthseg", "SynthSeg"]
for p in pkgs:
    print(("FOUND: " if importlib.util.find_spec(p) else "NOT FOUND: ") + f"python module {p}")
PY
fi

# Check a few common filesystem locations used by FreeSurfer / FastSurfer-style installs
SYN_PATHS=$(ls -d /usr/local/synthseg* /opt/synthseg* "$HOME"/synthseg* 2>/dev/null || true)
if [ -n "$SYN_PATHS" ]; then
  found "SynthSeg-related directories:"
  printf "%s\n" "$SYN_PATHS"
fi

echo
echo "Done."
