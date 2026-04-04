#!/usr/bin/env bash

# run_fastsurfer_docker.sh ::
# Run FastSurfer in Docker for one or all subjects.
# Outputs are written to:
#   <BASE_DIR>/<SUBJECT>/FastSurfer/<SUBJECT>/...

set -euo pipefail

if [ "$#" -lt 3 ] || [ "$#" -gt 4 ]; then
    echo "Usage: $0 <processed_base_dir> <threads> <use_cuda> [<subject_id>]"
    echo ""
    echo "  threads   : number of threads (e.g. 8)"
    echo "  use_cuda  : 0 for CPU, 1 for GPU (Linux + NVIDIA)"
    echo ""
    echo "Example:"
    echo "  $0 /export01/data/Ethan-COMP-401 8 0"
    echo "  $0 /export01/data/Ethan-COMP-401 8 1 MS_001"
    exit 1
fi

BASE_DIR="$1"          # e.g. /export01/data/Ethan-COMP-401
THREADS="$2"           # e.g. 8
USE_CUDA="$3"          # 0 = CPU, 1 = GPU
SUBJECT_ID="${4:-}"    # optional single subject

FASTSURFER_IMAGE="${FASTSURFER_IMAGE:-deepmi/fastsurfer:latest}"
FS_LICENSE_PATH="${FS_LICENSE_PATH:-${FS_LICENSE:-}}"

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

if [ "$USE_CUDA" = "1" ]; then
    if ! docker info --format '{{json .Runtimes}}' 2>/dev/null | grep -q nvidia; then
        echo "WARNING: NVIDIA Docker runtime not detected. Falling back to CPU mode."
        USE_CUDA="0"
    fi
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

    local t1_for_fastsurfer="$t1_dir/${subject_name}_RAW_T1_T1.nii.gz"
    if [ ! -f "$t1_for_fastsurfer" ]; then
        t1_for_fastsurfer="$t1_dir/${subject_name}_RAW_T1.nii.gz"
    fi

    if [ ! -f "$t1_for_fastsurfer" ]; then
        echo "[$subject_name] No T1 input found (RAW_T1). Skipping."
        return
    fi

    mkdir -p "$fs_subjects_dir"

    local done_marker="$fs_subjects_dir/${subject_name}/scripts/recon-surf.done"
    if [ -f "$done_marker" ]; then
        echo "[$subject_name] FastSurfer output already present. Skipping."
        return
    fi

    local docker_gpu_args=()
    local fastsurfer_mode_args=(--no_cuda)
    if [ "$USE_CUDA" = "1" ]; then
        docker_gpu_args=(--gpus all)
        fastsurfer_mode_args=()
    fi

    echo "[$subject_name] Running FastSurfer Docker on $t1_for_fastsurfer"
    DOCKER_CONTENT_TRUST=0 docker run --rm -t \
        --user "$(id -u):$(id -g)" \
        "${docker_gpu_args[@]}" \
        -v "$subject_dir:/subject" \
        -v "$FS_LICENSE_PATH:/fs_license/license.txt:ro" \
        "$FASTSURFER_IMAGE" \
        --fs_license /fs_license/license.txt \
        --t1 "/subject/T1/$(basename "$t1_for_fastsurfer")" \
        --sid "$subject_name" \
        --sd /subject/FastSurfer \
        --threads "$THREADS" \
        --parallel \
        --no_hypothal \
        "${fastsurfer_mode_args[@]}"

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
