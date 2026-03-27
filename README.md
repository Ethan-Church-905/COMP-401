# COMP-401
Winter 2026 COMP 401 Project

### Main Goals ###
1. Compute Probabilistic tractography for all subjects from the thalamus to different cortical regions
2. Compute and track DWI metrics of along-tract MS pathology
3. Correlate along-tract MS pathology with metrics of cortical MS pathology

### Data Setup ###

```
~/Data/
└── subject_ID/
    ├── T1/
    │   ├── {Raw_T1}.nii
    │   ├── {FreeSurfer_Processed_T1}.nii
    │   └── Rois/
    │       ├── {Raw_Rois}.nii
    │       └── {Registered_Rois}.nii
    ├── DWI/
    │   ├── {Raw_DWI}.nii
    │   ├── {Brain_Extracted_DWI}.nii
    │   └── Metrics/
    │       └── {DWI_Metrics}.nii
    └── Tractography/
        └── {all_tractography_files}
```


- The raw data is all contained in the folder: '/data/rudko/Ethan_COMP401' on the rumour desktop
- T1 Data should be in folder: /data/rudko/Ethan_COMP401/{subject_ID}/MP2RAGE_1mm/MP2RAGE_1mm_UNI_Images_Series0004
- DWI Data is in the folder /data/rudko/Ethan_COMP401/{subject_ID}/cmrr_mbep2d_diff_acc6_b2500
- Preprocessing Bash scripts are in the 'preprocessing' directory
- These scripts are called by the scheduling scripts in the 'scheduler_scripts' directory



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

- These steps are performed by the scheduler script ___.sh and __.sh

### Analyis Pathway ###
1. Sample the DWI metrics along the tract at some number of locations(100?) 
2. Compare to MTsat and cortical thickness from 7T space




