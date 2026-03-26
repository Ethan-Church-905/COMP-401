#!/bin/bash

# fs_segmentation.sh :: Script to perform FreeSurfer recon-all on T1-weighted MRI scans
# for multiple subjects or a single subject.

# Check if the correct number of arguments is provided
if [ "$#" -lt 2 ] || [ "$#" -gt 3 ]; then
    echo "Usage: $0 <nifti_base_dir> <freesurfer_subjects_dir> [<subject_id>]"
    exit 1
fi

# Define input parameters
NIFTI_BASE_DIR="$1"
OUTPUT_BASE_DIR="$2"   # This will be used as FreeSurfer SUBJECTS_DIR
SUBJECT_ID="$3"        # Optional subject ID to process a single subject

# Log input parameters for reference
echo "NIfTI base directory: $NIFTI_BASE_DIR"
echo "FreeSurfer SUBJECTS_DIR: $OUTPUT_BASE_DIR"
[ -n "$SUBJECT_ID" ] && echo "Processing only for subject: $SUBJECT_ID" || echo "Processing all subjects"

echo "Starting FreeSurfer recon-all for T1 scans..."
START_TIME=$(date "+%Y-%m-%d %H:%M:%S")
echo "Processing started at: $START_TIME"

# Function to process a single subject
segment_subject() {
    local subject_name="$1"
    local t1_nifti_file="$NIFTI_BASE_DIR/$subject_name/T1/${subject_name}_T1.nii.gz"

    if [ ! -f "$t1_nifti_file" ]; then
        echo "T1 file not found for subject $subject_name at $t1_nifti_file. Skipping."
        return
    fi

    # Optional: skip if recon-all already completed
    if [ -f "$OUTPUT_BASE_DIR/$subject_name/scripts/recon-all.done" ]; then
        echo "recon-all already completed for subject $subject_name. Skipping."
        return
    fi

    echo "Running recon-all for subject $subject_name on $t1_nifti_file"

    # Call FreeSurfer recon-all
    recon-all \
        -sd "$OUTPUT_BASE_DIR" \
        -s "$subject_name" \
        -i "$t1_nifti_file" \
        -all
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
echo "FreeSurfer recon-all completed for T1 scans."
