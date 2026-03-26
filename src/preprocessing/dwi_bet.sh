#!/bin/bash

# dwi_bet.sh :: Script to perform brain extraction on diffusion weighted images (DWI)
# for multiple subjects or a single subject using FSL's BET tool.
# Uses the first volume (b=0) to derive a brain mask and applies it to the full DWI.

if [ "$#" -lt 4 ] || [ "$#" -gt 5 ]; then
    echo "Usage: $0 <NIFTI_BASE_DIR> <OUT_SUB_DIR> <FILE_SUFFIX> <fractional_intensity_threshold> [<subject_id>]"
    exit 1
fi

# Input parameters
NIFTI_BASE_DIR="$1"      # e.g., /path/to/nifti
OUT_SUB_DIR="$2"         # e.g., DWI
FILE_SUFFIX="$3"         # e.g., DWI
FRAC_THRESH="$4"         # e.g., 0.3
SUBJECT_ID="$5"          # optional

echo "DWI NIfTI base directory: $NIFTI_BASE_DIR"
echo "DWI subdirectory: $OUT_SUB_DIR"
echo "DWI file suffix: $FILE_SUFFIX"
echo "BET fractional intensity threshold: $FRAC_THRESH"
[ -n "$SUBJECT_ID" ] && echo "Processing only subject: $SUBJECT_ID" || echo "Processing all subjects"

process_subject() {
    local subject="$1"
    local parent="$NIFTI_BASE_DIR/$subject/$OUT_SUB_DIR"
    local dwi_file="$parent/${subject}_${FILE_SUFFIX}.nii.gz"

    if [ ! -f "$dwi_file" ]; then
        echo "DWI file not found for subject $subject at $dwi_file. Skipping."
        return
    fi

    local name_dwi
    name_dwi="$(basename "${dwi_file%.nii*}")"

    # Skip if final output already exists
    if [ -f "$parent/${name_dwi}_noskull.nii.gz" ]; then
        echo "Brain-extracted DWI already exists for subject $subject. Skipping."
        return
    fi

    echo "Running BET for subject $subject on $dwi_file"

    mkdir -p "$parent/tmp"
    cp "$dwi_file" "$parent/tmp"

    # Save current directory and move to tmp
    local old_pwd="$PWD"
    cd "$parent/tmp" || { echo "Failed to cd to $parent/tmp"; return; }

    # Split all volumes; first is assumed b=0 image
    fslsplit "$name_dwi"

    # Move b=0 volume back to parent
    mv "$parent/tmp/vol0000.nii.gz" "$parent/${name_dwi}_b0.nii.gz"

    # Return to previous directory
    cd "$old_pwd"

    # Brain extraction on b0
    bet "$parent/${name_dwi}_b0.nii.gz" \
        "$parent/${name_dwi}_b0_noskull" \
        -R -m -f "$FRAC_THRESH"

    # Apply mask to full DWI
    fslmaths "$dwi_file" \
        -mas "$parent/${name_dwi}_b0_noskull_mask.nii.gz" \
        "$parent/${name_dwi}_noskull.nii.gz"

    # Clean up
    rm -rf "$parent/tmp"

    echo "Finished BET for subject $subject"
}

if [ -n "$SUBJECT_ID" ]; then
    process_subject "$SUBJECT_ID"
else
    for subject_dir in "$NIFTI_BASE_DIR"/*/; do
        subject_name=$(basename "$subject_dir")
        process_subject "$subject_name"
    done
fi