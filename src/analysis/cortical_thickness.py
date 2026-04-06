"""
cortical_thickness.py :: extracts mean cortical thickness at the motor cortex (precentral gyrus)
from FastSurfer surface reconstructions, for each hemisphere and each subject.

Usage: python cortical_thickness.py <base_dir> <output_csv>
    base_dir   : directory containing subject folders with FastSurfer output
                  (expected layout: <base_dir>/<subject>/FastSurfer/<subject>/...)
    output_csv : path to write the resulting CSV summary
"""

import sys
import os
from os.path import join as pjoin
import numpy as np
import nibabel as nib
import pandas as pd

# The precentral gyrus label in the DKT atlas corresponds to the primary motor cortex
MOTOR_CORTEX_LABEL = 'precentral'


def get_motor_cortex_thickness(fs_subject_dir, hemi):
    """Return mean cortical thickness of the precentral gyrus for one hemisphere.

    Parameters
    ----------
    fs_subject_dir : str
        Path to the FastSurfer subject directory (e.g. .../FastSurfer/<subject>).
    hemi : str
        'lh' or 'rh'.

    Returns
    -------
    float
        Mean cortical thickness in mm, or NaN if data is unavailable.
    """
    thickness_path = pjoin(fs_subject_dir, 'surf', f'{hemi}.thickness')
    annot_path = pjoin(fs_subject_dir, 'label', f'{hemi}.aparc.DKTatlas.annot')

    if not os.path.exists(thickness_path) or not os.path.exists(annot_path):
        return float('nan')

    # Load per-vertex thickness values
    thickness = nib.freesurfer.read_morph_data(thickness_path)

    # Load annotation: labels per vertex, color table, and region names
    labels, ctab, names = nib.freesurfer.read_annot(annot_path)

    # Decode region names if they are bytes
    names = [n.decode('utf-8') if isinstance(n, bytes) else n for n in names]

    if MOTOR_CORTEX_LABEL not in names:
        return float('nan')

    motor_idx = names.index(MOTOR_CORTEX_LABEL)
    motor_mask = labels == motor_idx

    if not np.any(motor_mask):
        return float('nan')

    return float(np.nanmean(thickness[motor_mask]))


def get_whole_brain_thickness(fs_subject_dir, hemi):
    """Return the mean cortical thickness across all vertices for one hemisphere.

    Parameters
    ----------
    fs_subject_dir : str
        Path to the FastSurfer subject directory.
    hemi : str
        'lh' or 'rh'.

    Returns
    -------
    float
        Mean cortical thickness in mm, or NaN if data is unavailable.
    """
    thickness_path = pjoin(fs_subject_dir, 'surf', f'{hemi}.thickness')
    if not os.path.exists(thickness_path):
        return float('nan')

    thickness = nib.freesurfer.read_morph_data(thickness_path)
    # Exclude zero-thickness vertices (medial wall / non-cortical)
    cortical = thickness[thickness > 0]
    if len(cortical) == 0:
        return float('nan')
    return float(np.nanmean(cortical))


def cortical_thickness(base_dir, output_csv):
    """Extract whole-brain and motor cortex thickness for all subjects and save to CSV."""
    subjects = sorted([
        s for s in os.listdir(base_dir)
        if os.path.isdir(pjoin(base_dir, s))
    ])

    records = []

    for subject in subjects:
        fs_subject_dir = pjoin(base_dir, subject, 'FastSurfer', subject)

        if not os.path.isdir(fs_subject_dir):
            print(f"Warning: FastSurfer output not found for {subject}, skipping.")
            continue

        lh_thickness = get_motor_cortex_thickness(fs_subject_dir, 'lh')
        rh_thickness = get_motor_cortex_thickness(fs_subject_dir, 'rh')
        lh_whole = get_whole_brain_thickness(fs_subject_dir, 'lh')
        rh_whole = get_whole_brain_thickness(fs_subject_dir, 'rh')

        records.append({
            'subject': subject,
            'lh_precentral_thickness': lh_thickness,
            'rh_precentral_thickness': rh_thickness,
            'lh_whole_brain_thickness': lh_whole,
            'rh_whole_brain_thickness': rh_whole,
        })
        print(f"Processed {subject}: motor lh={lh_thickness:.4f}, rh={rh_thickness:.4f}, "
              f"whole lh={lh_whole:.4f}, rh={rh_whole:.4f}")

    results = pd.DataFrame(records)
    results.to_csv(output_csv, index=False)
    print(f"Saved motor cortex thickness to {output_csv}")


if __name__ == "__main__":
    base_dir = sys.argv[1]
    output_csv = sys.argv[2]
    cortical_thickness(base_dir, output_csv)
