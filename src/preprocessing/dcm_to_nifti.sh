#!/bin/bash

# dcm_to_nifti.sh :: Script to convert DICOM files to NIfTI format for multiple subjects or a single subject using dcm2niix.
# This script serves as a wrapper to call the specific conversion scripts for T1 and DWI scans, ensuring that both types of scans are processed for each subject.

# Base directories
BASE_DICOM_DIR=/data/rudko/Ethan_COMP401
NIFTI_BASE_DIR=/export01/data/Ethan-COMP-401

# Output subdirectories
T1_OUT_SUB_DIR=T1
DWI_OUT_SUB_DIR=DWI

# T1 folders to process (4 total inside {subject_ID}/MP2RAGE_1mm/)
# Each entry: "SEARCH_TERM:FILE_SUFFIX"
T1_FOLDERS=(
    "MP2RAGE_1mm_T1_Images_Series000[0-9]:RAW_T1"
    "MP2RAGE_1mm_UNI_Images_Series000[0-9]:RAW_T1_UNI"
)

# DWI folders to process (6 total)
# Each entry: "SEARCH_TERM:FILE_SUFFIX"
DWI_FOLDERS=(
    "cmrr_mbep2d_diff_acc6_b2500:RAW_DWI_b2500"
    "cmrr_mbep2d_diff_acc6_b2500_PA:RAW_DWI_b2500_PA"
    "cmrr_mbep2d_diff_acc6_b300:RAW_DWI_b300"
    "cmrr_mbep2d_diff_acc6_b300_PA:RAW_DWI_b300_PA"
    "cmrr_mbep2d_diff_acc6_b700:RAW_DWI_b700"
    "cmrr_mbep2d_diff_acc6_b700_PA:RAW_DWI_b700_PA"
)

# Set to a specific subject ID to process only that subject, or leave empty to process all subjects
SUBJECT_ID=""

echo "Starting DICOM to NIfTI conversion for T1 and DWI scans..."

# Convert all 4 T1 folders
'''
echo "Converting T1 scans (4 folders per subject)..."
for t1_entry in "${T1_FOLDERS[@]}"; do
    # Parse the entry (format: SEARCH_TERM:FILE_SUFFIX)
    T1_SEARCH_TERM="${t1_entry%%:*}"
    T1_FILE_SUFFIX="${t1_entry##*:}"
    
    echo "Processing T1 folder: $T1_SEARCH_TERM"
    
    if [ -n "$SUBJECT_ID" ]; then
        ./convert_dicom_to_nifti_T1.sh "$BASE_DICOM_DIR" "$NIFTI_BASE_DIR" "$T1_OUT_SUB_DIR" "$T1_SEARCH_TERM" "$T1_FILE_SUFFIX" "$SUBJECT_ID"
    else
        ./convert_dicom_to_nifti_T1.sh "$BASE_DICOM_DIR" "$NIFTI_BASE_DIR" "$T1_OUT_SUB_DIR" "$T1_SEARCH_TERM" "$T1_FILE_SUFFIX"
    fi
done
'''

# Convert all 6 DWI folders
echo "Converting DWI scans (6 folders per subject)..."
for dwi_entry in "${DWI_FOLDERS[@]}"; do
    # Parse the entry (format: SEARCH_TERM:FILE_SUFFIX)
    DWI_SEARCH_TERM="${dwi_entry%%:*}"
    DWI_FILE_SUFFIX="${dwi_entry##*:}"
    
    echo "Processing DWI folder: $DWI_SEARCH_TERM"
    
    if [ -n "$SUBJECT_ID" ]; then
        ./convert_dicom_to_nifti_dwi.sh "$BASE_DICOM_DIR" "$NIFTI_BASE_DIR" "$DWI_OUT_SUB_DIR" "$DWI_SEARCH_TERM" "$DWI_FILE_SUFFIX" "$SUBJECT_ID"
    else
        ./convert_dicom_to_nifti_dwi.sh "$BASE_DICOM_DIR" "$NIFTI_BASE_DIR" "$DWI_OUT_SUB_DIR" "$DWI_SEARCH_TERM" "$DWI_FILE_SUFFIX"
    fi
done

echo "DICOM to NIfTI conversion completed for T1 and DWI scans."





