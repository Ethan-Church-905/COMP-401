#!/bin/bash

# compute_dwi_metrics.sh :: script to compute DWI metrics (e.g., FA, MD) for multiple subjects or a single subject using MRtrix 3.

if [ "$#" -lt 3 ] || [ "$#" -gt 4 ]; then
    echo "Usage: $0 <NIFTI_BASE_DIR> <DWI_SUB_DIR> <DWI_SUFFIX> [<subject_id>]"
    exit 1
fi 

# Parse input
NIFTI_BASE_DIR="$1"    # e.g., /path/to/nifti
DWI_SUB_DIR="$2"       # e.g., DWI
DWI_SUFFIX="$3"        # e.g., RAW_DWI_noskull
SUBJECT_ID="$4"        # optional

echo "DWI NIfTI base directory: $NIFTI_BASE_DIR"
echo "DWI subdirectory: $DWI_SUB_DIR"
echo "DWI file suffix: $DWI_SUFFIX"
[ -n "$SUBJECT_ID" ] && echo "Processing only subject: $SUBJECT_ID" || echo "Processing all subjects"

process_subject() {
    local subject_name="$1"

    local dwi_dir="$NIFTI_BASE_DIR/$subject_name/$DWI_SUB_DIR"
    local dwi_file="$dwi_dir/${subject_name}_${DWI_SUFFIX}.nii.gz"
    local bval_file="$dwi_dir/${subject_name}_${DWI_SUFFIX}.bval"
    local bvec_file="$dwi_dir/${subject_name}_${DWI_SUFFIX}.bvec"

    if [ ! -f "$dwi_file" ]; then
        echo "DWI file not found for subject $subject_name at $dwi_file. Skipping."
        return
    fi

    if [ ! -f "$bval_file" ] || [ ! -f "$bvec_file" ]; then
        echo "bval/bvec not found for subject $subject_name in $dwi_dir. Skipping."
        return
    fi

    # Output metrics to DWI/Metrics/ subdirectory per organizational setup
    local metrics_dir="$dwi_dir/Metrics"
    mkdir -p "$metrics_dir"

    local dwi_name="${subject_name}_${DWI_SUFFIX}"

    # Skip if FA already exists (assume all metrics generated together)
    if [ -f "$metrics_dir/${dwi_name}_fa.nii.gz" ]; then
        echo "DWI metrics already exist for subject $subject_name. Skipping."
        return
    fi

    echo "Computing DWI metrics for subject $subject_name"

    # Generate the metric maps using MRtrix
    dwi2tensor "$dwi_file" - -fslgrad "$bvec_file" "$bval_file" | \
    tensor2metric - \
        -adc "$metrics_dir/${dwi_name}_md.nii.gz" \
        -ad "$metrics_dir/${dwi_name}_ad.nii.gz" \
        -rd "$metrics_dir/${dwi_name}_rd.nii.gz" \
        -fa "$metrics_dir/${dwi_name}_fa.nii.gz"

    echo "Finished DWI metrics for subject $subject_name"
}

if [ -n "$SUBJECT_ID" ]; then
    process_subject "$SUBJECT_ID"
else
    for subject_dir in "$NIFTI_BASE_DIR"/*/; do
        subject_name=$(basename "$subject_dir")
        process_subject "$subject_name"
    done
fi

echo "DWI metrics computation complete."
