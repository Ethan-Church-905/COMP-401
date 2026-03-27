#!/usr/bin/env bash

# roi_registration.sh :: Register FreeSurfer ROIs (brainstem + motor cortex/precentral)
# to DWI space for multiple subjects or a single subject.
#
# This script is a multi-subject wrapper around Viet Hoang's original reg_roi
# script and is designed to be compatible with:
#   - fs_segmentation.sh (for running FreeSurfer recon-all)
#   - roi_conversion.sh  (for creating aparc+aseg-based ROI masks)
#   - dwi_bet.sh         (for generating the b=0 DWI image)
#
# Expected directory / filename layout per subject:
#   T1 / FreeSurfer (after fs_segmentation + conversion of brain.mgz):
#       <FREESURFER_SUBJECTS_DIR>/<SUBJECT>/mri/brain.nii.gz
#   ROIs (after roi_conversion.sh):
#       <NIFTI_BASE_DIR>/<SUBJECT>/T1/Rois/
#           aparc+aseg_16_brainstem.nii.gz
#           aparc+aseg_1024_lh_precentral.nii.gz
#           aparc+aseg_2024_rh_precentral.nii.gz
#
#   DWI (after convert_dicom_to_nifti_dwi.sh + dwi_bet.sh):
#       <NIFTI_BASE_DIR>/<SUBJECT>/<DWI_SUB_DIR>/<SUBJECT>_<DWI_SUFFIX>_b0.nii.gz

if [ "$#" -lt 4 ] || [ "$#" -gt 5 ]; then
	echo "Usage: $0 <NIFTI_BASE_DIR> <DWI_SUB_DIR> <DWI_SUFFIX> <FREESURFER_SUBJECTS_DIR> [<SUBJECT_ID>]"
	exit 1
fi

NIFTI_BASE_DIR="$1"          # e.g., /path/to/nifti
DWI_SUB_DIR="$2"             # e.g., DWI
DWI_SUFFIX="$3"              # e.g., DWI
SUBJECTS_DIR="$4"            # FreeSurfer SUBJECTS_DIR
SUBJECT_ID="$5"              # optional

echo "DWI NIfTI base directory: $NIFTI_BASE_DIR"
echo "DWI subdirectory: $DWI_SUB_DIR"
echo "DWI file suffix: $DWI_SUFFIX"
echo "FreeSurfer SUBJECTS_DIR: $SUBJECTS_DIR"
[ -n "$SUBJECT_ID" ] && echo "Processing only subject: $SUBJECT_ID" || echo "Processing all subjects"

register_subject() {
	local subject_name="$1"

	local t1_file="$SUBJECTS_DIR/$subject_name/mri/brain.nii.gz"
	local dwi_dir="$NIFTI_BASE_DIR/$subject_name/$DWI_SUB_DIR"
	local b0_file="$dwi_dir/${subject_name}_${DWI_SUFFIX}_b0.nii.gz"

	# ROIs are now in NIFTI_BASE_DIR/subject/T1/Rois/ per organizational setup
	local roi_dir="$NIFTI_BASE_DIR/$subject_name/T1/Rois"
	local roi_bs="$roi_dir/aparc+aseg_16_brainstem.nii.gz"
	local roi_mc_lh="$roi_dir/aparc+aseg_1024_lh_precentral.nii.gz"
	local roi_mc_rh="$roi_dir/aparc+aseg_2024_rh_precentral.nii.gz"

	# Basic existence checks
	if [ ! -f "$t1_file" ]; then
		echo "T1 brain file not found for subject $subject_name at $t1_file. Skipping."
		return
	fi

	if [ ! -f "$b0_file" ]; then
		echo "b0 DWI file not found for subject $subject_name at $b0_file. Skipping."
		return
	fi

	if [ ! -f "$roi_bs" ] || [ ! -f "$roi_mc_lh" ] || [ ! -f "$roi_mc_rh" ]; then
		echo "One or more ROI masks missing for subject $subject_name in $roi_dir. Skipping."
		return
	fi

	echo "Registering ROIs to DWI space for subject $subject_name"

	local file_t1w="$t1_file"          # brain.nii.gz (brain.mgz converted to NIfTI)
	local file_b0="$b0_file"           # b0 image in DWI space
	local file_roi_bs="$roi_bs"        # Brain stem mask
	local file_roi_mc_lh="$roi_mc_lh"  # Left motor cortex (precentral) mask
	local file_roi_mc_rh="$roi_mc_rh"  # Right motor cortex (precentral) mask

	# Output registered ROIs to T1/Rois/ directory per organizational setup
	local output_dir="$roi_dir"

	# Determine the names of each of these files
	local t1w_name
	local roi_bs_name
	local roi_mc_lh_name
	local roi_mc_rh_name

	t1w_name="$(basename "${file_t1w%.nii*}")"
	roi_bs_name="$(basename "${file_roi_bs%.nii*}")"
	roi_mc_lh_name="$(basename "${file_roi_mc_lh%.nii*}")"
	roi_mc_rh_name="$(basename "${file_roi_mc_rh%.nii*}")"

	# Make a tmp folder that will be deleted at the end of the script
	local tmp_dir
	mkdir -p "$output_dir/${t1w_name}_T1w_2_DWI_tmp"
	tmp_dir="$output_dir/${t1w_name}_T1w_2_DWI_tmp"

	# 1. Register DWI_b0 to T1w using FLIRT; we obtain the matrix DWI_b0_reg_2_T1w
	flirt -dof 6 -cost mutualinfo \
		-in "$file_b0" -ref "$file_t1w" \
		-omat "$tmp_dir/DWI_b0_reg_2_T1w_tmp.mat"

	# 2. Convert DWI_b0_reg_2_T1w matrix to MRtrix format
	transformconvert -quiet \
		"$tmp_dir/DWI_b0_reg_2_T1w_tmp.mat" "$file_b0" "$file_t1w" flirt_import \
		"$tmp_dir/DWI_b0_reg_2_T1w_tmp.txt"

	# 3. Apply the inverse of the DWI_b0_reg_2_T1w matrix to obtain T1w_DTIsp
	mrtransform -quiet "$file_t1w" \
		-inverse -linear "$tmp_dir/DWI_b0_reg_2_T1w_tmp.txt" \
		"$output_dir/${t1w_name}_DTIsp.nii.gz"

	# 4. Apply the inverse of the DWI_b0_reg_2_T1w matrix to label masks
	mrtransform -quiet "$file_roi_bs" \
		-inverse -linear "$tmp_dir/DWI_b0_reg_2_T1w_tmp.txt" \
		"$output_dir/${roi_bs_name}_DTIsp.nii.gz"

	mrtransform -quiet "$file_roi_mc_lh" \
		-inverse -linear "$tmp_dir/DWI_b0_reg_2_T1w_tmp.txt" \
		"$output_dir/${roi_mc_lh_name}_DTIsp.nii.gz"

	mrtransform -quiet "$file_roi_mc_rh" \
		-inverse -linear "$tmp_dir/DWI_b0_reg_2_T1w_tmp.txt" \
		"$output_dir/${roi_mc_rh_name}_DTIsp.nii.gz"

	# Remove tmp folder
	rm -r "$tmp_dir"

	echo "Finished ROI registration for subject $subject_name"
}

if [ -n "$SUBJECT_ID" ]; then
	register_subject "$SUBJECT_ID"
else
	for subject_dir in "$NIFTI_BASE_DIR"/*/; do
		subject_name=$(basename "$subject_dir")
		register_subject "$subject_name"
	done
fi

echo "ROI registration complete."