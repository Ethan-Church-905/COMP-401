#!/usr/bin/env bash

# run_fastsurfer_docker.sh ::
# Run FastSurfer in Docker for one or all subjects.
# Outputs are written to:
#   <BASE_DIR>/<SUBJECT>/FastSurfer/<SUBJECT>/...

set -euo pipefail

if [ "$#" -lt 1 ] || [ "$#" -gt 2 ]; then
    echo "Usage: $0 <processed_base_dir> [<subject_id>]"
    echo ""
    echo "Example:"
    echo "  $0 /export01/data/Ethan-COMP-401"
    echo "  $0 /export01/data/Ethan-COMP-401 MS_001"
    exit 1
fi

BASE_DIR="$1"          # e.g. /export01/data/Ethan-COMP-401
SUBJECT_ID="${2:-}"    # optional single subject

FASTSURFER_IMAGE="${FASTSURFER_IMAGE:-deepmi/fastsurfer:latest}"
FS_LICENSE_PATH="${FS_LICENSE_PATH:-${FS_LICENSE:-}}"
THREADS="${THREADS:-8}"

echo "Processed base directory: $BASE_DIR"
[ -n "$SUBJECT_ID" ] && echo "Processing only subject: $SUBJECT_ID" || echo "Processing all subjects"

if ! command -v docker >/dev/null 2>&1; then
    echo "ERROR: docker is not available in PATH."
    exit 1
fi

if [ -z "$FS_LICENSE_PATH" ] || [ ! -f "$FS_LICENSE_PATH" ]; then
    echo "ERROR: FreeSurfer license file not found."
    echo "Set FS_LICENSE_PATH (or FS_LICENSE) to your license file path."
    echo "Example: export FS_LICENSE_PATH=/path/to/license.txt"
    exit 1
fi

process_subject() {
    local subject_name="$1"
    local subject_dir="$BASE_DIR/$subject_name"
    local t1_dir="$subject_dir/T1"
    local fs_subjects_dir="$subject_dir/FastSurfer"

    if [ ! -d "$t1_dir" ]; then
        echo "[$subject_name] Missing T1 directory at $t1_dir. Skipping."
        return
    fi

    local t1_for_fastsurfer="$t1_dir/${subject_name}_RAW_T1.nii.gz"
    if [ ! -f "$t1_for_fastsurfer" ]; then
        t1_for_fastsurfer="$t1_dir/${subject_name}_RAW_T1_UNI_denoised.nii.gz"
        if [ ! -f "$t1_for_fastsurfer" ]; then
            t1_for_fastsurfer="$t1_dir/${subject_name}_RAW_T1_UNI.nii.gz"
        fi
    fi

    if [ ! -f "$t1_for_fastsurfer" ]; then
        echo "[$subject_name] No T1 input found (RAW_T1, denoised UNI, or UNI). Skipping."
        return
    fi

    mkdir -p "$fs_subjects_dir"

    local done_marker="$fs_subjects_dir/${subject_name}/scripts/recon-surf.done"
    if [ -f "$done_marker" ]; then
        echo "[$subject_name] FastSurfer output already present. Skipping."
        return
    fi

    echo "[$subject_name] Running FastSurfer Docker on $t1_for_fastsurfer"
    docker run --rm -t \
        -v "$subject_dir:/subject" \
        -v "$FS_LICENSE_PATH:/fs_license/license.txt:ro" \
        "$FASTSURFER_IMAGE" \
        --fs_license /fs_license/license.txt \
        --t1 "/subject/T1/$(basename "$t1_for_fastsurfer")" \
        --sid "$subject_name" \
        --sd /subject/FastSurfer \
        --threads "$THREADS" \
        --parallel \
        --no_cuda

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

echo "FastSurfer processing complete."
