#!/bin/bash

# fs_segmentation.sh :: Run FreeSurfer SynthSeg 2.0 parcellation on T1-weighted
# MRI scans for multiple subjects or a single subject.

# Check if the correct number of arguments is provided
if [ "$#" -lt 1 ] || [ "$#" -gt 2 ]; then
    echo "Usage: $0 <nifti_base_dir> [<subject_id>]"
    exit 1
fi

export CUDA_VISIBLE_DEVICES=""
# Define input parameters
NIFTI_BASE_DIR="$1"
SUBJECT_ID="$2"        # Optional subject ID to process a single subject

# Log input parameters for reference
echo "NIfTI base directory: $NIFTI_BASE_DIR"
[ -n "$SUBJECT_ID" ] && echo "Processing only for subject: $SUBJECT_ID" || echo "Processing all subjects"

echo "Starting FreeSurfer SynthSeg 2.0 processing for T1 scans..."
START_TIME=$(date "+%Y-%m-%d %H:%M:%S")
echo "Processing started at: $START_TIME"

if ! command -v mri_synthseg >/dev/null 2>&1; then
    echo "mri_synthseg is not available in PATH. Please source FreeSurfer with SynthSeg support."
    exit 1
fi

# Function to process a single subject
segment_subject() {
    local subject_name="$1"
    local t1_nifti_file="$NIFTI_BASE_DIR/$subject_name/T1/${subject_name}_RAW_T1_T1.nii.gz"
    local subject_mri_dir="$NIFTI_BASE_DIR/$subject_name/mri"
    local subject_scripts_dir="$NIFTI_BASE_DIR/$subject_name/scripts"
    local aparc_nifti="$subject_mri_dir/aparc+aseg.nii.gz"
    local synthseg_brainmask="$subject_mri_dir/brainmask.nii.gz"
    local synthseg_brain="$subject_mri_dir/brain.nii.gz"

    if [ ! -f "$t1_nifti_file" ]; then
        echo "T1 file not found for subject $subject_name at $t1_nifti_file. Skipping."
        return
    fi

    mkdir -p "$subject_mri_dir" "$subject_scripts_dir"

    # Optional: skip if SynthSeg aparc output already exists
    if [ -f "$aparc_nifti" ]; then
        echo "SynthSeg segmentation already exists for subject $subject_name. Skipping."
        return
    fi

    echo "Running mri_synthseg (--parc) for subject $subject_name on $t1_nifti_file"

    # Generate an aparc+aseg-like parcellation in NIfTI format for downstream ROI extraction.
    mri_synthseg \
        --i "$t1_nifti_file" \
        --o "$aparc_nifti" \
        --parc \
        --cpu

    if [ $? -ne 0 ]; then
        echo "mri_synthseg failed for subject $subject_name."
        return
    fi

    # Create brainmask/brain image for compatibility with existing tooling.
    fslmaths "$aparc_nifti" -bin "$synthseg_brainmask"
    fslmaths "$t1_nifti_file" -mul "$synthseg_brainmask" "$synthseg_brain"

    touch "$subject_scripts_dir/synthseg.done"
}

if [ -n "$SUBJECT_ID" ]; then
    # Process only the specified subject
    segment_subject "$SUBJECT_ID"
else
    # Process all subjects in the NIFTI_BASE_DIR
    for subject_dir in "$NIFTI_BASE_DIR"/*/; do
        subject_name=$(basename "$subject_dir")
        segment_subject "$subject_name"
    done
fi

END_TIME=$(date "+%Y-%m-%d %H:%M:%S")
echo "Processing completed at: $END_TIME"
echo "FreeSurfer SynthSeg processing completed for T1 scans."
