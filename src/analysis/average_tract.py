"""
average_tract.py :: computes the average values for FA,MD, on the tract as a whole and returns them
"""

import pickle
import sys
import os
from os.path import join as pjoin
import numpy as np
import pandas as pd
from utils import load_nifti, load_tck, get_tract_profile, get_tract_length

if __name__ == "__main__":

    # Base directory containing all subject data
    base = sys.argv[1]
    out = sys.argv[3]

    # List of subjects to process
    subjects = sorted(os.listdir(base))

    for subject in subjects:
    #compute a single average value of a diffusion metric for a tract for each subject, and save it.
        print(f"Processing {subject}...")

        b0_path = pjoin(base, subject, 'dwi', subject[:-3]+'_dwi_b0_noskull.nii.gz')
        
        lh_path = pjoin(base, subject, 'cst', subject[:-3]+'_lh_cst_edit.tck')
        rh_path = pjoin(base, subject, 'cst', subject[:-3]+'_rh_cst_edit.tck')
        
        lh = load_tck(lh_path, b0_path).streamlines        
        rh = load_tck(rh_path, b0_path).streamlines

        metric_path = pjoin(base, subject, 'metrics', 
                            subject[:-3]+'_dwi_noskull_'+metric_name+'.nii.gz')
        metric_img, metric_aff = load_nifti(metric_path)

        lesion_path = pjoin(base, subject, 'lesion', subject[:-3]+'_ct2f_dtisp.nii.gz')
        lesion_img, lesion_aff = load_nifti(lesion_path)

        
        # Get the along tract profile of the metric (FA, MD, etc.)
        lh_profile = get_tract_profile(lh, metric_img, metric_aff, 
                                        use_weights=True)
        # Get the along tract profile of the metric (FA, MD, etc.)
        rh_profile = get_tract_profile(rh, metric_img, metric_aff, 
                                        use_weights=True)
        lh_metric_df[subj] = np.mean(lh_profile)
        rh_metric_df[subj] = np.mean(rh_profile)
        # Find out which part of the tract intesects the roi
        lh_lesion_profile = get_tract_profile(lh, lesion_img, lesion_aff)
        rh_lesion_profile = get_tract_profile(rh, lesion_img, lesion_aff)
        lh_lesion_df[subj] = np.mean(lh_lesion_profile)        
        rh_lesion_df[subj] = np.mean(rh_lesion_profile)