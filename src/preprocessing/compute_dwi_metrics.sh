#!/bin/bash

# compute_dwi_metrics.sh :: script to compute DWI metrics (e.g., FA, MD) for multiple subjects or a single subject using MRtrix 3.

if [ "$#" -lt 3 ] || [ "$#" -gt 4 ]; then
    echo "Usage: $0 <bval_file> <bvec_file> <DWI_file> [<subject_id>]"
    exit 1
fi 

# Parse input
BVAL_FILE="$1"
BVEC_FILE="$2"
DWI_FILE="$3"
SUBJECT_ID="$4"       

# Get the parent directory of the DWI and the name of the DWI
parent="$(dirname "$DWI_FILE")"
dwi_name="$(basename ${DWI_FILE%.nii*})"

# Output metrics to DWI/Metrics/ subdirectory per organizational setup
metrics_dir="$parent/Metrics"
mkdir -p "$metrics_dir"

generate_maps(){
    # Generate the metric maps. This command is from MRtrix.
    dwi2tensor $DWI_FILE - -fslgrad $BVEC_FILE $BVAL_FILE | \
    tensor2metric - \
    -adc $metrics_dir/${dwi_name}_md.nii.gz \
    -ad $metrics_dir/${dwi_name}_ad.nii.gz \
    -rd $metrics_dir/${dwi_name}_rd.nii.gz \
    -fa $metrics_dir/${dwi_name}_fa.nii.gz
}

if [ -n "$SUBJECT_ID" ]; then
    process_subject "$SUBJECT_ID"
else
    for subject_dir in "$NIFTI_BASE_DIR"/*/; do
        subject_name=$(basename "$subject_dir")
        process_subject "$subject_name"
    done
fi

echo "CST tract generation complete."
