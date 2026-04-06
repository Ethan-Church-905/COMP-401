"""
average_brain.py :: computes the whole-brain average of each diffusion metric (FA, MD, AD, RD) per subject,
by masking each metric map with the brain mask generated during DWI preprocessing.

Usage: python average_brain.py <base_dir> <output_csv>
    base_dir   : directory containing subject folders with DWI outputs from DWI_processing.py
    output_csv : path to write the resulting CSV summary
"""

import sys
import os
from os.path import join as pjoin
import numpy as np
import nibabel as nib
import pandas as pd

METRICS = ['fa', 'md', 'ad', 'rd']


def average_brain(base_dir, output_csv):
    """Compute the mean value of each DTI metric within the brain mask for every subject."""
    subjects = sorted([
        s for s in os.listdir(base_dir)
        if os.path.isdir(pjoin(base_dir, s))
    ])

    records = []

    for subject in subjects:
        subject_dir = pjoin(base_dir, subject)

        # Resolve the DWI directory (may be subject_dir itself or subject_dir/DWI)
        dwi_dir = subject_dir
        if os.path.isdir(pjoin(subject_dir, 'DWI')):
            dwi_dir = pjoin(subject_dir, 'DWI')

        mask_path = pjoin(dwi_dir, 'dwi_AP_combined_denoised_degibbs_1stVol_brain_mask.nii.gz')
        if not os.path.exists(mask_path):
            print(f"Warning: mask not found for {subject}, skipping.")
            continue

        mask = nib.load(mask_path).get_fdata().astype(bool)

        row = {'subject': subject}
        for metric_name in METRICS:
            metric_path = pjoin(dwi_dir, f'{subject}_dti_{metric_name}_dipy.nii.gz')
            if not os.path.exists(metric_path):
                print(f"Warning: {metric_name} map not found for {subject}, skipping metric.")
                row[metric_name] = float('nan')
                continue

            metric_data = nib.load(metric_path).get_fdata()
            row[metric_name] = np.nanmean(metric_data[mask])

        records.append(row)
        print(f"Processed {subject}")

    results = pd.DataFrame(records)
    results.to_csv(output_csv, index=False)
    print(f"Saved whole-brain averages to {output_csv}")


if __name__ == "__main__":
    base_dir = sys.argv[1]
    output_csv = sys.argv[2]
    average_brain(base_dir, output_csv)
