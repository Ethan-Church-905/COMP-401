# COMP-401
Winter 2026 COMP 401 Project

### Main Goals ###
1. Compute Probabilistic tractography for all subjects from the thalamus to different cortical regions
2. Compute and track DWI metrics of along-tract MS pathology
3. Correlate along-tract MS pathology with metrics of cortical MS pathology

### Data Setup ###
The data is all contained in the folder: '/data/rudko/Ethan_COMP401' on the rumour desktop
T1 Data should be in folder: /data/rudko/Ethan_COMP401/HC_EDL_039_27-07-22_3T/MP2RAGE_1mm/MP2RAGE_1mm_UNI_Images_Series0004
DWI 

Preprocessing Bash scripts are in the 'preprocessing' directory
These scripts are called by the scheduling scripts in the 'scheduler_scripts' directory

### Project Structure ###

├── env_utils/                                  # Folder containing environment setup scripts.  
├── misc/                                       # Folder containing temporary code that was tried.  
├── src/                                        # Source code folder.  
│   ├── analysis                                # Folder containing code for statistical analysis.  
│   │   ├──. 
│   ├── preprocessing                           # Folder containing all preprocessing scripts.  
│   │   ├──. 
│   └── scheduler_scripts                       # Folder containing SGE scripts used in the project.   
│       ├──.     
├── viets_code/                                 # Code taken directly from Viet's work. 
└── readme.md                                   # README file (this file). 


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



