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

DWI_DICOM_DIR=/data/rudko/Ethan_COMP401/{subject}/
T1_DICOM_DIR=/data/rudko/Ethan_COMP401/{subject}/MP2RAGE_1mm
NIFTI_BASE_DIR=/data/rudko/Ethan_COMP401/{subject}/preprocessing/nifti_output
T1_OUT_SUB_DIR=T1
DWI_OUT_SUB_DIR=DWI
T1_FILE_SUFFIX=_T1
DWI_FILE_SUFFIX=_DWI
SUBJECT_ID=""  # Set to a specific subject ID to process only that subject, or leave empty to process all subjects

echo "Starting DICOM to NIfTI conversion for T1 and DWI scans..."

convert_dicom_to_nifti_T1.sh $T1_DICOM_DIR $T1_DICOM_DIR $NIFTI_BASE_DIR $T1_OUT_SUB_DIR $T1_FILE_SUFFIX [$SUBJECT_ID]
convert_dicom_to_nifti_dwi.sh $DWI_DICOM_DIR $DWI_DICOM_DIR $NIFTI_BASE_DIR $DWI_OUT_SUB_DIR $DWI_FILE_SUFFIX [$SUBJECT_ID]

echo "DICOM to NIfTI conversion completed for T1 and DWI scans."





