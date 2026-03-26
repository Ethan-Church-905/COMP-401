#!/bin/bash

# roi_conversion.sh :: Convert FreeSurfer aparc+aseg segmentations into binary ROI masks
# for multiple subjects or a single subject, compatible with fs_segmentation.sh output.
#
# Expected inputs (matching fs_segmentation.sh):
#   - FreeSurfer SUBJECTS_DIR containing one folder per subject (e.g. SF_001)
#   - Each subject directory must contain mri/aparc+aseg.mgz
#
# For each subject, this script will:
#   1. Convert aparc+aseg.mgz to NIfTI aparc+aseg.nii.gz (if needed)
#   2. Extract binary ROIs for:
#        - Thalamus (L/R)
#        - Brainstem
#        - Precentral gyrus (L/R)
#        - Cingulum (isthmus cingulate, rostral anterior cingulate; L/R)
#        - Rostral middle frontal (L/R)
#        - Supramarginal gyrus (L/R)
#        - Caudal middle frontal (L/R)
#
# Usage:
#   roi_conversion.sh <freesurfer_subjects_dir> [<subject_id>]

if [ "$#" -lt 1 ] || [ "$#" -gt 2 ]; then
	echo "Usage: $0 <freesurfer_subjects_dir> [<subject_id>]"
	exit 1
fi

SUBJECTS_DIR="$1"
SUBJECT_ID="$2"   # optional

echo "FreeSurfer SUBJECTS_DIR: $SUBJECTS_DIR"
[ -n "$SUBJECT_ID" ] && echo "Processing only subject: $SUBJECT_ID" || echo "Processing all subjects"

process_subject() {
	local subject_name="$1"
	local subject_dir="$SUBJECTS_DIR/$subject_name"
	local mgz_file="$subject_dir/mri/aparc+aseg.mgz"
	local aparc_nifti="$subject_dir/mri/aparc+aseg.nii.gz"

	if [ ! -d "$subject_dir" ]; then
		echo "Subject directory not found: $subject_dir. Skipping."
		return
	fi

	if [ ! -f "$mgz_file" ] && [ ! -f "$aparc_nifti" ]; then
		echo "No aparc+aseg file found for subject $subject_name (expected $mgz_file or $aparc_nifti). Skipping."
		return
	fi

	# Convert MGZ to NIfTI if needed
	if [ ! -f "$aparc_nifti" ]; then
		echo "Converting $mgz_file to NIfTI for subject $subject_name..."
		mri_convert "$mgz_file" "$aparc_nifti"
		if [ $? -ne 0 ]; then
			echo "mri_convert failed for subject $subject_name. Skipping."
			return
		fi
	fi

	local parent
	parent="$(dirname "$aparc_nifti")"

	# Creates an output folder
	mkdir -p "$parent/roi"

	local file_aparc="$aparc_nifti"

	echo "Creating ROIs for subject $subject_name from $file_aparc"

	# Corticospinal tract:
	# Brain stem
	fslmaths "$file_aparc" \
		-thr 16 -uthr 16 -bin \
		"$parent/roi/aparc+aseg_16_brainstem.nii.gz"
	# Precentral gyrus (LH)
	fslmaths "$file_aparc" \
		-thr 1024 -uthr 1024 -bin \
		"$parent/roi/aparc+aseg_1024_lh_precentral.nii.gz"
	# Precentral gyrus (RH)
	fslmaths "$file_aparc" \
		-thr 2024 -uthr 2024 -bin \
		"$parent/roi/aparc+aseg_2024_rh_precentral.nii.gz"

	# Cingulum:
	# Isthmus cingulate (LH)
	fslmaths "$file_aparc" \
		-thr 1010 -uthr 1010 -bin \
		"$parent/roi/aparc+aseg_1010_lh_isthmuscingulate.nii.gz"
	# Isthmus cingulate (RH)
	fslmaths "$file_aparc" \
		-thr 2010 -uthr 2010 -bin \
		"$parent/roi/aparc+aseg_2010_rh_isthmuscingulate.nii.gz"
	# Rostral anterior cingulate (LH)
	fslmaths "$file_aparc" \
		-thr 1026 -uthr 1026 -bin \
		"$parent/roi/aparc+aseg_1026_lh_rostralanteriorcingulate.nii.gz"
	# Rostral anterior cingulate (RH)
	fslmaths "$file_aparc" \
		-thr 2026 -uthr 2026 -bin \
		"$parent/roi/aparc+aseg_2026_rh_rostralanteriorcingulate.nii.gz"

	# Anterior thalamic radiation:
	# Rostral middle frontal (LH)
	fslmaths "$file_aparc" \
		-thr 1027 -uthr 1027 -bin \
		"$parent/roi/aparc+aseg_1027_lh_rostralmiddlefrontal.nii.gz"
	# Rostral middle frontal (RH)
	fslmaths "$file_aparc" \
		-thr 2027 -uthr 2027 -bin \
		"$parent/roi/aparc+aseg_2027_rh_rostralmiddlefrontal.nii.gz"
	# Thalamus (Left)
	fslmaths "$file_aparc" \
		-thr 10 -uthr 10 -bin \
		"$parent/roi/aparc+aseg_10_left_thalamus.nii.gz"
	# Thalamus (Right)
	fslmaths "$file_aparc" \
		-thr 49 -uthr 49 -bin \
		"$parent/roi/aparc+aseg_49_right_thalamus.nii.gz"

	# Superior longitudinal fasciculus:
	# Supra marginal gyrus (LH)
	fslmaths "$file_aparc" \
		-thr 1031 -uthr 1031 -bin \
		"$parent/roi/aparc+aseg_1031_lh_supramarginal.nii.gz"
	# Supra marginal gyrus (RH)
	fslmaths "$file_aparc" \
		-thr 2031 -uthr 2031 -bin \
		"$parent/roi/aparc+aseg_2031_rh_supramarginal.nii.gz"
	# Caudal middle frontal (LH)
	fslmaths "$file_aparc" \
		-thr 1003 -uthr 1003 -bin \
		"$parent/roi/aparc+aseg_1003_lh_caudalmiddlefrontal.nii.gz"
	# Caudal middle frontal (RH)
	fslmaths "$file_aparc" \
		-thr 2003 -uthr 2003 -bin \
		"$parent/roi/aparc+aseg_2003_rh_caudalmiddlefrontal.nii.gz"

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