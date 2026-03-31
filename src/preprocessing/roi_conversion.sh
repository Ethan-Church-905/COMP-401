#!/bin/bash

# roi_conversion.sh :: Convert SynthSeg/FreeSurfer aparc+aseg segmentations into
# binary ROI masks for multiple subjects or a single subject.
#
# Expected inputs (matching fs_segmentation.sh SynthSeg output):
#   - SynthSeg output directory containing one folder per subject (e.g. SF_001)
#   - Each subject directory should contain mri/aparc+aseg.nii.gz
#
# For each subject, this script will:
#   1. Load aparc+aseg segmentation from SynthSeg output
#   2. Extract binary ROIs for:
#        - Thalamus (L/R)
#        - Brainstem
#        - Precentral gyrus (L/R)
#        - Paracentral lobule (L/R)
#        - Motor cortex (combined precentral + paracentral; L/R)
#        - Cingulum (isthmus cingulate, rostral anterior cingulate; L/R)
#        - Rostral middle frontal (L/R)
#        - Supramarginal gyrus (L/R)
#        - Caudal middle frontal (L/R)
#
# Usage:
#   roi_conversion.sh <synthseg_subjects_dir> <nifti_base_dir> [<subject_id>]

if [ "$#" -lt 2 ] || [ "$#" -gt 3 ]; then
	echo "Usage: $0 <synthseg_subjects_dir> <nifti_base_dir> [<subject_id>]"
	exit 1
fi

SUBJECTS_DIR="$1"
NIFTI_BASE_DIR="$2"
SUBJECT_ID="$3"   # optional

echo "SynthSeg subjects directory: $SUBJECTS_DIR"
echo "NIfTI base directory: $NIFTI_BASE_DIR"
[ -n "$SUBJECT_ID" ] && echo "Processing only subject: $SUBJECT_ID" || echo "Processing all subjects"

extract_binary_roi() {
	local aparc_file="$1"
	local label="$2"
	local output_file="$3"
	local label_name="$4"

	echo "  - Extracting $label_name (label $label)"
	fslmaths "$aparc_file" -thr "$label" -uthr "$label" -bin "$output_file"

	if [ $? -ne 0 ]; then
		echo "Failed to extract ROI: $label_name"
		return 1
	fi
}

combine_rois() {
	local roi_a="$1"
	local roi_b="$2"
	local output_file="$3"
	local roi_name="$4"

	echo "  - Combining into $roi_name"
	fslmaths "$roi_a" -add "$roi_b" -bin "$output_file"

	if [ $? -ne 0 ]; then
		echo "Failed to combine ROIs for: $roi_name"
		return 1
	fi
}

process_subject() {
	local subject_name="$1"
	local subject_dir="$SUBJECTS_DIR/$subject_name"
	local aparc_nifti="$subject_dir/mri/aparc+aseg.nii.gz"
	local synthseg_parc_nifti="$subject_dir/mri/synthseg_parc.nii.gz"
	local mgz_file="$subject_dir/mri/aparc+aseg.mgz"
	local file_aparc=""

	if [ ! -d "$subject_dir" ]; then
		echo "Subject directory not found: $subject_dir. Skipping."
		return
	fi

	if [ -f "$aparc_nifti" ]; then
		file_aparc="$aparc_nifti"
	elif [ -f "$synthseg_parc_nifti" ]; then
		file_aparc="$synthseg_parc_nifti"
	elif [ -f "$mgz_file" ]; then
		echo "Converting $mgz_file to NIfTI for subject $subject_name..."
		mri_convert "$mgz_file" "$aparc_nifti"
		if [ $? -ne 0 ]; then
			echo "mri_convert failed for subject $subject_name. Skipping."
			return
		fi
		file_aparc="$aparc_nifti"
	else
		echo "No SynthSeg/aparc segmentation found for subject $subject_name (expected $aparc_nifti). Skipping."
		return
	fi

	# Output ROIs to NIFTI_BASE_DIR/subject/T1/Rois/ per organizational setup
	local roi_output_dir="$NIFTI_BASE_DIR/$subject_name/T1/Rois"

	# Creates an output folder
	mkdir -p "$roi_output_dir"

	echo "Creating ROIs for subject $subject_name from $file_aparc"

	# Extract single-label ROIs
	local roi_specs
	roi_specs=$(cat <<'EOF'
16|aparc+aseg_16_brainstem.nii.gz|Brainstem
1024|aparc+aseg_1024_lh_precentral.nii.gz|Precentral gyrus (LH)
2024|aparc+aseg_2024_rh_precentral.nii.gz|Precentral gyrus (RH)
1017|aparc+aseg_1017_lh_paracentral.nii.gz|Paracentral lobule (LH)
2017|aparc+aseg_2017_rh_paracentral.nii.gz|Paracentral lobule (RH)
1010|aparc+aseg_1010_lh_isthmuscingulate.nii.gz|Isthmus cingulate (LH)
2010|aparc+aseg_2010_rh_isthmuscingulate.nii.gz|Isthmus cingulate (RH)
1026|aparc+aseg_1026_lh_rostralanteriorcingulate.nii.gz|Rostral anterior cingulate (LH)
2026|aparc+aseg_2026_rh_rostralanteriorcingulate.nii.gz|Rostral anterior cingulate (RH)
1027|aparc+aseg_1027_lh_rostralmiddlefrontal.nii.gz|Rostral middle frontal (LH)
2027|aparc+aseg_2027_rh_rostralmiddlefrontal.nii.gz|Rostral middle frontal (RH)
10|aparc+aseg_10_left_thalamus.nii.gz|Thalamus (Left)
49|aparc+aseg_49_right_thalamus.nii.gz|Thalamus (Right)
1031|aparc+aseg_1031_lh_supramarginal.nii.gz|Supramarginal gyrus (LH)
2031|aparc+aseg_2031_rh_supramarginal.nii.gz|Supramarginal gyrus (RH)
1003|aparc+aseg_1003_lh_caudalmiddlefrontal.nii.gz|Caudal middle frontal (LH)
2003|aparc+aseg_2003_rh_caudalmiddlefrontal.nii.gz|Caudal middle frontal (RH)
EOF
)

	while IFS='|' read -r label output_name roi_name; do
		extract_binary_roi "$file_aparc" "$label" "$roi_output_dir/$output_name" "$roi_name" || return
	done <<< "$roi_specs"

	# Motor cortex (combined precentral + paracentral) per hemisphere
	combine_rois \
		"$roi_output_dir/aparc+aseg_1024_lh_precentral.nii.gz" \
		"$roi_output_dir/aparc+aseg_1017_lh_paracentral.nii.gz" \
		"$roi_output_dir/aparc+aseg_lh_motorcortex.nii.gz" \
		"Motor cortex (LH)" || return

	combine_rois \
		"$roi_output_dir/aparc+aseg_2024_rh_precentral.nii.gz" \
		"$roi_output_dir/aparc+aseg_2017_rh_paracentral.nii.gz" \
		"$roi_output_dir/aparc+aseg_rh_motorcortex.nii.gz" \
		"Motor cortex (RH)" || return

	echo "Finished ROIs for subject $subject_name"
}

if [ -n "$SUBJECT_ID" ]; then
	process_subject "$SUBJECT_ID"
else
	for subject_dir in "$SUBJECTS_DIR"/*/; do
		subject_name=$(basename "$subject_dir")
		process_subject "$subject_name"
	done
fi

echo "ROI conversion complete."