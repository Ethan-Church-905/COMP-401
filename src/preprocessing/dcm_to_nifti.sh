#!/bin/bash

# dcm_to_nifti.sh :: Script to convert DICOM files to NIfTI format for multiple subjects or a single subject using dcm2niix.
# This script serves as a wrapper to call the specific conversion scripts for T1 and DWI scans, ensuring that both types of scans are processed for each subject.

# call dcm_to_nifti.sh with the following arguments:
# 1. DWI DICOM directory is /data/rudko/Ethan_COMP401/{subject}/...
# 2. T1 DICOM directory (e.g., /path/to/t1/directory)
# 3. Base output directory for NIfTI files (e.g., /path/to/nifti/output)
# 4. Output subdirectory for the converted files (e.g., "converted_scans")
# 5. File name suffix to use for the converted files (e.g., "version1")
# 6. Optional subject ID to process a single subject (e.g., "subject01") - if not provided, the script will process all subjects in the specified directories.

# Base directories
BASE_DICOM_DIR=/data/rudko/Ethan_COMP401
NIFTI_BASE_DIR=~/Data

# Output subdirectories
T1_OUT_SUB_DIR=T1
DWI_OUT_SUB_DIR=DWI

# Search terms to find the correct DICOM folders within each subject
# T1: {subject_ID}/MP2RAGE_1mm/MP2RAGE_1mm_UNI_Images_Series0004
# DWI: {subject_ID}/cmrr_mbep2d_diff_acc6_b2500
T1_SEARCH_TERM="MP2RAGE_1mm_UNI_Images_Series0004"
DWI_SEARCH_TERM="cmrr_mbep2d_diff_acc6_b2500"

# File suffixes for output files
T1_FILE_SUFFIX=RAW_T1
DWI_FILE_SUFFIX=RAW_DWI

# Set to a specific subject ID to process only that subject, or leave empty to process all subjects
SUBJECT_ID=""

echo "Starting DICOM to NIfTI conversion for T1 and DWI scans..."

# Call conversion scripts (pass SUBJECT_ID only if it's set)
if [ -n "$SUBJECT_ID" ]; then
    convert_dicom_to_nifti_T1.sh "$BASE_DICOM_DIR" "$NIFTI_BASE_DIR" "$T1_OUT_SUB_DIR" "$T1_SEARCH_TERM" "$T1_FILE_SUFFIX" "$SUBJECT_ID"
    convert_dicom_to_nifti_dwi.sh "$BASE_DICOM_DIR" "$NIFTI_BASE_DIR" "$DWI_OUT_SUB_DIR" "$DWI_SEARCH_TERM" "$DWI_FILE_SUFFIX" "$SUBJECT_ID"
else
    convert_dicom_to_nifti_T1.sh "$BASE_DICOM_DIR" "$NIFTI_BASE_DIR" "$T1_OUT_SUB_DIR" "$T1_SEARCH_TERM" "$T1_FILE_SUFFIX"
    convert_dicom_to_nifti_dwi.sh "$BASE_DICOM_DIR" "$NIFTI_BASE_DIR" "$DWI_OUT_SUB_DIR" "$DWI_SEARCH_TERM" "$DWI_FILE_SUFFIX"
fi

echo "DICOM to NIfTI conversion completed for T1 and DWI scans."





