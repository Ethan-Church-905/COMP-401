#!/usr/bin/env bash

# denoise_t1_uni.sh ::
# Denoise UNI T1w images with MRtrix for one or all subjects.

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

echo "Processed base directory: $BASE_DIR"
[ -n "$SUBJECT_ID" ] && echo "Processing only subject: $SUBJECT_ID" || echo "Processing all subjects"

if ! command -v mrconvert >/dev/null 2>&1; then
    echo "ERROR: MRtrix command mrconvert is not available in PATH."
    exit 1
fi

if ! command -v mrfilter >/dev/null 2>&1; then
    echo "ERROR: MRtrix command mrfilter is not available in PATH."
    exit 1
fi

process_subject() {
    local subject_name="$1"
    local subject_dir="$BASE_DIR/$subject_name"
    local t1_dir="$subject_dir/T1"
    local tmp_dir="$subject_dir/T1/.mrtrix_tmp"

    if [ ! -d "$t1_dir" ]; then
        echo "[$subject_name] Missing T1 directory at $t1_dir. Skipping."
        return
    fi

    local uni_in="$t1_dir/${subject_name}_RAW_T1_UNI.nii.gz"
    if [ ! -f "$uni_in" ]; then
        uni_in=$(find "$t1_dir" -maxdepth 1 -type f \( -name "*UNI*.nii" -o -name "*UNI*.nii.gz" \) | head -n 1 || true)
    fi

    if [ -z "$uni_in" ] || [ ! -f "$uni_in" ]; then
        echo "[$subject_name] Could not find a UNI image in $t1_dir. Skipping."
        return
    fi

    mkdir -p "$tmp_dir"

    local uni_denoised="$t1_dir/${subject_name}_RAW_T1_UNI_denoised.nii.gz"
    local uni_mif="$tmp_dir/uni.mif"
    local uni_denoised_mif="$tmp_dir/uni_denoised.mif"

    if [ -f "$uni_denoised" ]; then
        echo "[$subject_name] Denoised UNI already exists: $uni_denoised"
        return
    fi

    echo "[$subject_name] Denoising UNI with MRtrix..."
    mrconvert "$uni_in" "$uni_mif" -force
    mrfilter "$uni_mif" denoise "$uni_denoised_mif" -force
    mrconvert "$uni_denoised_mif" "$uni_denoised" -force

    echo "[$subject_name] Wrote denoised UNI: $uni_denoised"
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

echo "UNI denoising complete."
