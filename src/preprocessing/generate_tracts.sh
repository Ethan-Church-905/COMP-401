#!/usr/bin/env bash

# generate_tracts.sh :: Multi-subject wrapper to reconstruct the corticospinal
# tract using probabilistic tractography (MRtrix 3), structured similarly to
# fs_segmentation.sh.
#
# For each subject, this script:
#   1. Loads the DWI, bval, bvec, and b0 mask from the NIfTI DWI directory
#   2. Loads the DWI-space ROIs (brainstem + precentral gyri) registered via
#      roi_registration.sh (aparc+aseg_*_DTIsp.nii.gz)
#   3. Runs MSMT-CSD and generates FODs
#   4. Generates left/right CST streamlines using the ROIs as seeds/includes
#
# Expected per-subject layout (matching other preprocessing scripts):
#   DWI:
#     <NIFTI_BASE_DIR>/<SUBJECT>/<DWI_SUB_DIR>/
#       <SUBJECT>_<DWI_SUFFIX>.nii.gz
#       <SUBJECT>_<DWI_SUFFIX>.bval
#       <SUBJECT>_<DWI_SUFFIX>.bvec
#       <SUBJECT>_<DWI_SUFFIX>_b0_noskull_mask.nii.gz   (from dwi_bet.sh)
#       (fallbacks: _b0_noskull.nii.gz, _b0.nii.gz)
#
#   ROIs in DWI space (after roi_conversion.sh + roi_registration.sh):
#     <NIFTI_BASE_DIR>/<SUBJECT>/T1/Rois/
#       aparc+aseg_16_brainstem_DTIsp.nii.gz
#       aparc+aseg_1024_lh_precentral_DTIsp.nii.gz
#       aparc+aseg_2024_rh_precentral_DTIsp.nii.gz
#

if [ "$#" -lt 3 ] || [ "$#" -gt 4 ]; then
    echo "Usage: $0 <NIFTI_BASE_DIR> <DWI_SUB_DIR> <DWI_SUFFIX> [<SUBJECT_ID>]"
    exit 1
fi

NIFTI_BASE_DIR="$1"      # e.g., /path/to/nifti
DWI_SUB_DIR="$2"         # e.g., DWI
DWI_SUFFIX="$3"          # e.g., DWI
SUBJECT_ID="$4"          # optional

echo "DWI NIfTI base directory: $NIFTI_BASE_DIR"
echo "DWI subdirectory: $DWI_SUB_DIR"
echo "DWI file suffix: $DWI_SUFFIX"
[ -n "$SUBJECT_ID" ] && echo "Processing only subject: $SUBJECT_ID" || echo "Processing all subjects"

process_subject() {
    local subject_name="$1"

    local dwi_dir="$NIFTI_BASE_DIR/$subject_name/$DWI_SUB_DIR"
    local file_dwi="$dwi_dir/${subject_name}_${DWI_SUFFIX}.nii.gz"
    local file_bval="$dwi_dir/${subject_name}_${DWI_SUFFIX}.bval"
    local file_bvec="$dwi_dir/${subject_name}_${DWI_SUFFIX}.bvec"

    # Determine b0 / mask file with fallbacks
    local file_b0=""
    if [ -f "$dwi_dir/${subject_name}_${DWI_SUFFIX}_b0_noskull_mask.nii.gz" ]; then
        file_b0="$dwi_dir/${subject_name}_${DWI_SUFFIX}_b0_noskull_mask.nii.gz"
    elif [ -f "$dwi_dir/${subject_name}_${DWI_SUFFIX}_b0_noskull.nii.gz" ]; then
        file_b0="$dwi_dir/${subject_name}_${DWI_SUFFIX}_b0_noskull.nii.gz"
    elif [ -f "$dwi_dir/${subject_name}_${DWI_SUFFIX}_b0.nii.gz" ]; then
        file_b0="$dwi_dir/${subject_name}_${DWI_SUFFIX}_b0.nii.gz"
    fi

    # ROIs in DWI space (DTIsp) from roi_registration.sh - now in T1/Rois/
    local dir_roi="$NIFTI_BASE_DIR/$subject_name/T1/Rois"
    local roi_bs="$dir_roi/aparc+aseg_16_brainstem_DTIsp.nii.gz"
    local roi_mc_lh="$dir_roi/aparc+aseg_1024_lh_precentral_DTIsp.nii.gz"
    local roi_mc_rh="$dir_roi/aparc+aseg_2024_rh_precentral_DTIsp.nii.gz"

    # Basic existence checks
    if [ ! -f "$file_dwi" ]; then
        echo "DWI file not found for subject $subject_name at $file_dwi. Skipping."
        return
    fi

    if [ ! -f "$file_bval" ] || [ ! -f "$file_bvec" ]; then
        echo "bval/bvec not found for subject $subject_name in $dwi_dir. Skipping."
        return
    fi

    if [ -z "$file_b0" ] || [ ! -f "$file_b0" ]; then
        echo "b0 / mask file not found for subject $subject_name in $dwi_dir. Skipping."
        return
    fi

    if [ ! -f "$roi_bs" ] || [ ! -f "$roi_mc_lh" ] || [ ! -f "$roi_mc_rh" ]; then
        echo "One or more DWI-space ROIs missing for subject $subject_name in $dir_roi. Skipping."
        return
    fi

    local name="$subject_name"
    echo "Generating CST tracts for subject $subject_name"

    # Output to Tractography/ directory per organizational setup
    local tract_base="$NIFTI_BASE_DIR/$subject_name/Tractography"
    mkdir -p "$tract_base"
    local dir_output="$tract_base"
    mkdir -p "$tract_base/cst"
    local dir_tract="$tract_base"

    # 1. Convert the DWI into an uncompressed format.
    mrconvert -quiet -fslgrad "$file_bvec" "$file_bval" -datatype float32 -strides 0,0,0,1 \
        "$file_dwi" "$dir_output/DWI.mif"

    # 2. Estimate the multi-shell, multi-tissue response function
    dwi2response dhollander "$dir_output/DWI.mif" \
        "$dir_output/RF_WM.txt" "$dir_output/RF_GM.txt" "$dir_output/RF_CSF.txt" \
        -voxels "$dir_output/RF_voxels.mif" -nthreads 8

    # 3. Create an FOD image using multi-shell, multi-tissue constrained spherical
    # deconvolution (MSMT-CSD)
    dwi2fod msmt_csd -mask "$file_b0" \
        "$dir_output/DWI.mif" \
        "$dir_output/RF_WM.txt" "$dir_output/WM_FODs.mif" \
        "$dir_output/RF_GM.txt" "$dir_output/GM.mif" \
        "$dir_output/RF_CSF.txt" "$dir_output/CSF.mif" \
        -nthreads 8

    # 3a. View the FOD image (optional RGB tissue map)
    mrconvert "$dir_output/WM_FODs.mif" - -coord 3 0 | \
        mrcat "$dir_output/CSF.mif" "$dir_output/GM.mif" - "$dir_output/tissueRGB.mif" -axis 3
    # mrview "$dir_output/tissueRGB.mif" -odf.load_sh "$dir_output/WM_FODs.mif"

    # Reconstruct the CST using MRtrix's tckgen. For each hemisphere we
    # generate two tractograms (start->end, end->start) and then merge.
    mkdir -p "$dir_tract/cst"

    tckgen "$dir_output/WM_FODs.mif" "$dir_tract/cst/${name}_lh_cst_start_end.tck" \
        -crop_at_gmwmi -seed_image "$roi_mc_lh" \
        -include "$roi_bs" \
        -select 2.5k -cutoff 0.05 -quiet -stop -seed_unidirectional -nthreads 2 -angle 30 \
        &
    tckgen "$dir_output/WM_FODs.mif" "$dir_tract/cst/${name}_lh_cst_end_start.tck" \
        -crop_at_gmwmi -seed_image "$roi_bs" \
        -include "$roi_mc_lh" \
        -select 2.5k -cutoff 0.05 -stop -seed_unidirectional -nthreads 2 -angle 30 \
        &
    tckgen "$dir_output/WM_FODs.mif" "$dir_tract/cst/${name}_rh_cst_start_end.tck" \
        -crop_at_gmwmi -seed_image "$roi_mc_rh" \
        -include "$roi_bs" \
        -select 2.5k -cutoff 0.05 -quiet -stop -seed_unidirectional -nthreads 2 -angle 30 \
        &
    tckgen "$dir_output/WM_FODs.mif" "$dir_tract/cst/${name}_rh_cst_end_start.tck" \
        -crop_at_gmwmi -seed_image "$roi_bs" \
        -include "$roi_mc_rh" \
        -select 2.5k -cutoff 0.05 -quiet -stop -seed_unidirectional -nthreads 2 -angle 30 \
        &
    wait

    echo "Finished reconstructing CST for subject $subject_name"

    # Merge the two left CST tractograms
    tckedit "$dir_tract/cst/${name}_lh_cst_start_end.tck" \
        "$dir_tract/cst/${name}_lh_cst_end_start.tck" \
        "$dir_tract/cst/${name}_lh_cst.tck"

    # Merge the two right CST tractograms
    tckedit "$dir_tract/cst/${name}_rh_cst_start_end.tck" \
        "$dir_tract/cst/${name}_rh_cst_end_start.tck" \
        "$dir_tract/cst/${name}_rh_cst.tck"
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