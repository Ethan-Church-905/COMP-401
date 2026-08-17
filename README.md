# COMP-401
Winter 2026 COMP 401 Project

### Main Goals ###
1. Compute Probabilistic tractography for all subjects from the thalamus to different cortical regions
2. Compute and track DWI metrics of along-tract MS pathology
3. Correlate along-tract MS pathology with metrics of cortical MS pathology

### Data Setup ###

### RAW_DATA: ###
```
/data/rudko/Ethan_COMP401
└── subject_ID/
    ├── MP2RAGE_1mm/
    │   ├── MP2RAGE_1mm_T1_Images_Series00[0-9][0-9]/ # all DICOM containing folders
    │   ├── MP2RAGE_1mm_UNI_Images_Series00[0-9][0-9]/
    │   ├── MP2RAGE_1mm_INV1_Series00[0-9][0-9]/
    │   ├── MP2RAGE_1mm_INV2_Series00[0-9][0-9]/
    ├── cmrr_mbep2d_diff_acc6_b2500/ # Pair of PA and AP directories for each b = 2500, 700, 300
    │   ├── cmrr_mbep2d_diff_acc6_b2500_Series0009/ # Contains DICOMs
    └── cmrr_mbep2d_diff_acc6_b2500_PA/
        └── cmrr_mbep2d_diff_acc6_b2500_PA_Series00[0-9][0-9]/ # Contains DICOM
```

### Processed Data: ###

```
/export01/data/Ethan-COMP-401
└── subject_ID/
    ├── T1/
    │   ├── {Raw_T1}.nii
    │   ├── {Raw_T1_UNI}.nii
    
    │   ├── {FreeSurfer_Processed_T1}.nii
    │   └── Rois/
    │       ├── {Raw_Rois}.nii
    │       └── {Registered_Rois}.nii
    ├── FastSurfer/ #Contains output from fastsurfer reconstruction
    ├── DWI/
    │   ├── {Raw_DWI}.nii
    │   ├── {Brain_Extracted_DWI}.nii
    │   └── Metrics/
    │       └── {DWI_Metrics}.nii
    └── Tractography/
        └── {all_tractography_files}
```



### Project Structure ###

```
├── env_utils/          # Environment setup scripts
├── misc/               # Temporary/experimental code
├── src/                # Source code
│   ├── analysis/       # Statistical analysis code
│   ├── preprocessing/  # Preprocessing scripts
│   └── scheduler_scripts/  # SGE scheduling scripts
├── viets_code/         # Code from Viet's work
└── README.md           # This file
``` 


### Preprocessing Pipeline ###
1. Convert DICOM files to NII for T1 MP2RAGE scans and DWI scans
2. Perform brain extraction on the DWI images
3. Perform FS segmentation on the T1 images for the thalamus and cortical regions, then convert regions into ROIs and register them to DWI space
4. Compute DWI metrics on the DWI images
5. Perform Probabilistic Tractography on the DWI images


### Analyis Pathway ###
- NOTE: the csv files will be contained in the directory:





