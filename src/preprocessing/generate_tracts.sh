#!/usr/bin/env bash

# generate_tracts.sh :: Multi-subject wrapper to reconstruct thalamocortical
# tracts (motor cortex <-> thalamus) using probabilistic tractography (MRtrix 3).
#
# For each subject, this script:
#   1. Loads the processed DWI (AP_eddy_unwarped_denoised_degibbs.nii.gz) from DWI_processing.py
#   2. Loads DWI-space ROIs (motor cortex + thalamus) registered via roi_registration.sh
#   3. Runs MSMT-CSD and generates FODs
#   4. Generates bilateral thalamocortical tracts between motor cortex and thalamus
#
# Expected per-subject layout (matching DWI_processing.py + roi_registration.sh):
#   DWI (from DWI_processing.py):
#     <DWI_DATA_DIR>/<SUBJECT>/
#       AP_eddy_unwarped_denoised_degibbs.nii.gz
#       dwi_AP_combined.bval
#       dwi_AP_combined.bvec
#       combined_dwi_denoised_degibbs_1stVol_brain_mask.nii.gz (or AP_brain_mask.nii.gz)
#
#   ROIs in DWI space (from roi_registration.sh):
#     <DWI_DATA_DIR>/<SUBJECT>/T1/Rois/
#       aparc+aseg_lh_motorcortex_DTIsp.nii.gz
#       aparc+aseg_rh_motorcortex_DTIsp.nii.gz
#       aparc+aseg_10_left_thalamus_DTIsp.nii.gz
#       aparc+aseg_49_right_thalamus_DTIsp.nii.gz
#

if [ "$#" -lt 1 ] || [ "$#" -gt 2 ]; then
    echo "Usage: $0 <DWI_DATA_DIR> [<SUBJECT_ID>]"
    echo ""
    echo "Where:"
    echo "  <DWI_DATA_DIR>   - Base directory containing subject folders with DWI data (from DWI_processing.py)"
    echo "  <SUBJECT_ID>     - Optional: Process only this subject (must begin with HC)"
    exit 1
fi

DWI_DATA_DIR="$1"        # e.g., /export01/data/Ethan-COMP-401
SUBJECT_ID="$2"          # optional

echo "DWI data directory: $DWI_DATA_DIR"
[ -n "$SUBJECT_ID" ] && echo "Processing only subject: $SUBJECT_ID" || echo "Processing all subjects"

process_subject() {
    local subject_name="$1"

    local dwi_dir="$DWI_DATA_DIR/$subject_name/DWI"
    
    # DWI files from DWI_processing.py
    local file_dwi="$dwi_dir/AP_eddy_unwarped_denoised_degibbs.nii.gz"
    local file_bval="$dwi_dir/dwi_AP_combined.bval"
    local file_bvec="$dwi_dir/dwi_AP_combined.bvec"

    # Determine brain mask file with fallbacks from DWI_processing.py
    local file_b0=""
    if [ -f "$dwi_dir/combined_dwi_denoised_degibbs_1stVol_brain_mask.nii.gz" ]; then
        file_b0="$dwi_dir/combined_dwi_denoised_degibbs_1stVol_brain_mask.nii.gz"
    elif [ -f "$dwi_dir/AP_brain_mask.nii.gz" ]; then
        file_b0="$dwi_dir/AP_brain_mask.nii.gz"
    else
        echo "Brain mask file not found for subject $subject_name in $dwi_dir. Skipping."
        return
    fi

    # ROIs in DWI space (DTIsp) from roi_registration.sh - T1/Rois/ directory
    local dir_roi="$DWI_DATA_DIR/$subject_name/Rois"
    
    # Motor cortex ROIs (seed regions)
    local roi_mc_lh="$dir_roi/aparc+aseg_lh_motorcortex_DTIsp.nii.gz"
    local roi_mc_rh="$dir_roi/aparc+aseg_rh_motorcortex_DTIsp.nii.gz"
    
    # Thalamus ROIs (target/include regions)
    local roi_thal_l="$dir_roi/aparc+aseg_10_left_thalamus_DTIsp.nii.gz"
    local roi_thal_r="$dir_roi/aparc+aseg_49_right_thalamus_DTIsp.nii.gz"

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

    if [ ! -f "$roi_mc_lh" ] || [ ! -f "$roi_mc_rh" ] || [ ! -f "$roi_thal_l" ] || [ ! -f "$roi_thal_r" ]; then
        echo "One or more DWI-space ROIs missing for subject $subject_name in $dir_roi. Skipping."
        echo "  Expected: Motor cortex (L/R) and Thalamus (L/R) registered ROIs."
        return
    fi

    local name="$subject_name"
    echo "Generating thalamocortical tracts for subject $subject_name"

    # Output to Tractography/ directory per organizational setup
    local tract_base="$DWI_DATA_DIR/$subject_name/Tractography"
    mkdir -p "$tract_base"
    local dir_output="$tract_base"
    mkdir -p "$tract_base/thalamocortical"
    local dir_tract="$tract_base"

    #checks to see if the final tract files already exist, and skip processing if they do
    if [ -f "$dir_tract/thalamocortical/${name}_lh_thalamocortical.tck" ] && [ -f "$dir_tract/thalamocortical/${name}_rh_thalamocortical.tck" ]; then
        echo "Thalamocortical tracts already exist for subject $subject_name. Skipping tract generation."
        return
    fi

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

    # Reconstruct thalamocortical tracts using MRtrix's tckgen.
    # For each hemisphere we generate two tractograms (motor->thalamus, thalamus->motor) and merge.
    mkdir -p "$dir_tract/thalamocortical"

    # Left hemisphere: motor cortex to thalamus (seed -> include)
    tckgen "$dir_output/WM_FODs.mif" "$dir_tract/thalamocortical/${name}_lh_thcort_mc_to_thal.tck" \
        -crop_at_gmwmi -seed_image "$roi_mc_lh" \
        -include "$roi_thal_l" \
        -select 2.5k -cutoff 0.05 -quiet -stop -seed_unidirectional -nthreads 2 -angle 30 \
        &
    
    # Left hemisphere: thalamus to motor cortex (seed -> include)
    tckgen "$dir_output/WM_FODs.mif" "$dir_tract/thalamocortical/${name}_lh_thcort_thal_to_mc.tck" \
        -crop_at_gmwmi -seed_image "$roi_thal_l" \
        -include "$roi_mc_lh" \
        -select 2.5k -cutoff 0.05 -stop -seed_unidirectional -nthreads 2 -angle 30 \
        &
    
    # Right hemisphere: motor cortex to thalamus (seed -> include)
    tckgen "$dir_output/WM_FODs.mif" "$dir_tract/thalamocortical/${name}_rh_thcort_mc_to_thal.tck" \
        -crop_at_gmwmi -seed_image "$roi_mc_rh" \
        -include "$roi_thal_r" \
        -select 2.5k -cutoff 0.05 -quiet -stop -seed_unidirectional -nthreads 2 -angle 30 \
        &
    
    # Right hemisphere: thalamus to motor cortex (seed -> include)
    tckgen "$dir_output/WM_FODs.mif" "$dir_tract/thalamocortical/${name}_rh_thcort_thal_to_mc.tck" \
        -crop_at_gmwmi -seed_image "$roi_thal_r" \
        -include "$roi_mc_rh" \
        -select 2.5k -cutoff 0.05 -quiet -stop -seed_unidirectional -nthreads 2 -angle 30 \
        &
    wait

    echo "Finished reconstructing thalamocortical tracts for subject $subject_name"

    # Merge the two left thalamocortical tractograms
    tckedit "$dir_tract/thalamocortical/${name}_lh_thcort_mc_to_thal.tck" \
        "$dir_tract/thalamocortical/${name}_lh_thcort_thal_to_mc.tck" \
        "$dir_tract/thalamocortical/${name}_lh_thalamocortical.tck"

    # Merge the two right thalamocortical tractograms
    tckedit "$dir_tract/thalamocortical/${name}_rh_thcort_mc_to_thal.tck" \
        "$dir_tract/thalamocortical/${name}_rh_thcort_thal_to_mc.tck" \
        "$dir_tract/thalamocortical/${name}_rh_thalamocortical.tck"
}

if [ -n "$SUBJECT_ID" ]; then
    process_subject "$SUBJECT_ID"
else
    # Auto-discover all HC* subjects in the DWI data directory
    for subject_dir in "$DWI_DATA_DIR"/MS*/; do
        if [ ! -d "$subject_dir" ]; then
            continue
        fi
        subject_name=$(basename "$subject_dir")
        process_subject "$subject_name"
    done
fi

echo "Thalamocortical tract generation complete."