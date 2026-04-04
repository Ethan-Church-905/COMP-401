#!/usr/bin/env bash

# denoise_and_recon.sh :: compatibility wrapper
# Runs:
#   1) denoise_t1_uni.sh
#   2) run_fastsurfer_docker.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

"$SCRIPT_DIR/denoise_t1_uni.sh" "$@"
"$SCRIPT_DIR/run_fastsurfer_docker.sh" "$@"

echo "Combined denoise + FastSurfer workflow complete."
