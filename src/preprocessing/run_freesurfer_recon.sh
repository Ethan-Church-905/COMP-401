#!/usr/bin/env bash

# run_freesurfer_recon.sh ::
# Run FreeSurfer recon-all for one or all subjects.
# Outputs are written to:
#   <BASE_DIR>/<SUBJECT>/FreeSurfer/<SUBJECT>/...

set -euo pipefail

if [ "$#" -lt 2 ] || [ "$#" -gt 3 ]; then
    echo "Usage: $0 <processed_base_dir> <threads> [<subject_id>]"
    echo ""
    echo "  threads   : number of threads (e.g. 8)"
    echo ""
    echo "Example:"
    echo "  $0 /export01/data/Ethan-COMP-401 8"
    echo "  $0 /export01/data/Ethan-COMP-401 8 MS_001"
    exit 1
fi

BASE_DIR="$1"          # e.g. /export01/data/Ethan-COMP-401
THREADS="$2"           # e.g. 8
SUBJECT_ID="${3:-}"    # optional single subject

echo "Processed base directory: $BASE_DIR"
[ -n "$SUBJECT_ID" ] && echo "Processing only subject: $SUBJECT_ID" || echo "Processing all subjects"

if ! command -v recon-all >/dev/null 2>&1; then
    echo "ERROR: recon-all is not available in PATH."
    echo "Make sure FreeSurfer is installed and sourced (e.g. source \$FREESURFER_HOME/SetUpFreeSurfer.sh)."
    exit 1
fi

if [ -z "${FS_LICENSE:-}" ] && [ -z "${FREESURFER_HOME:-}" ]; then
    echo "ERROR: FREESURFER_HOME is not set."
    echo "Source your FreeSurfer setup script before running this."
    exit 1
fi

if [ -n "${FREESURFER_HOME:-}" ] && [ ! -f "$FREESURFER_HOME/license.txt" ]; then
    if [ -z "${FS_LICENSE:-}" ] || [ ! -f "${FS_LICENSE:-}" ]; then
        echo "ERROR: FreeSurfer license file not found."
        echo "Place license.txt in \$FREESURFER_HOME or set FS_LICENSE to your license file path."
        exit 1
    fi
fi

process_subject() {
    local subject_name="$1"
    local subject_dir="$BASE_DIR/$subject_name"
    local t1_dir="$subject_dir/T1"
    local fs_subjects_dir="$subject_dir/FreeSurfer"

    if [ ! -d "$t1_dir" ]; then
        echo "[$subject_name] Missing T1 directory at $t1_dir. Skipping."
        return
    fi

    local t1_input="$t1_dir/${subject_name}_RAW_T1_T1.nii.gz"
    if [ ! -f "$t1_input" ]; then
        t1_input="$t1_dir/${subject_name}_RAW_T1.nii.gz"
    fi

    if [ ! -f "$t1_input" ]; then
        echo "[$subject_name] No T1 input found (RAW_T1). Skipping."
        return
    fi

    mkdir -p "$fs_subjects_dir"

    local done_marker="$fs_subjects_dir/${subject_name}/scripts/recon-all.done"
    if [ -f "$done_marker" ]; then
        echo "[$subject_name] FreeSurfer output already present. Skipping."
        return
    fi

    echo "[$subject_name] Running recon-all on $t1_input"
    recon-all \
        -i "$t1_input" \
        -s "$subject_name" \
        -sd "$fs_subjects_dir" \
        -all \
        -openmp "$THREADS"

    echo "[$subject_name] Completed. Output: $fs_subjects_dir/$subject_name"
}

if [ -n "$SUBJECT_ID" ]; then
    process_subject "$SUBJECT_ID"
else
    for subject_path in "$BASE_DIR"/*; do
        [ -d "$subject_path" ] || continue
        subject_name="$(basename "$subject_path")"
        process_subject "$subject_name"
    done
fi

echo "FreeSurfer recon-all processing complete."
