import time
start = time.time()
import subprocess
import os
from nipype.interfaces.fsl import Reorient2Std, BET
from nipype.interfaces.ants.segmentation import BrainExtraction
from nipype.interfaces.ants import RegistrationSynQuick
import pandas as pd 
import shutil
import numpy as np
import nibabel as nib
from dipy.denoise.localpca import mppca
from dipy.segment.mask import median_otsu
from dipy.denoise.gibbs import gibbs_removal
from dipy.io.image import save_nifti
from dipy.core.gradients import gradient_table
import dipy.reconst.dti as dti
from dipy.reconst.dti import color_fa
import amico
import pandas as pd
import scipy.stats
from datetime import datetime
import json
import matplotlib.pyplot as plt
import glob
from mpl_toolkits.mplot3d import Axes3D
import math
from pathlib import Path
import re

path_to_ants = '/data/rudko/hannabe/conda/envs/py3/bin'
# path_to_data = '/data/rudko/hannabe/Code/data'
# path_to_data = '/data/rudko/hannabe/pc_mri'
path_to_data = '/export01/data/hannabe/Code/data'
path_to_scratch = '/data/rudko/hannabe/Code/scratch'
study = 'cihr_test_7t'
subjects = ['20260313', 'MS_DG_074', '20251014', '20250905']

path_to_study = '%s/%s' % (path_to_data, study)
mp2rage_file_start = 'anat-T1w_acq-mp2rage_0.7mm_CSptx'
t2star_file_start = 'anat-T2star_acq-me_gre_0.7iso_ASPIRE'
b1map_file_start = 'b1map_tra_p2'
mton_file_start = 'MTON'
mtoff_file_start = 'MTOFF'
t1w_file_start = 'T1W'
dwi_b0_pa_file_start = 'dwi_acq_b0_PA'
dwi_38dir_ap_file_start = 'dwi_acq_multib_38dir_AP_acc9_1p4'
dwi_70dir_ap_file_start = 'dwi_acq_multib_70dir_AP_acc9_1p4'

##################
# MAIN FUNCTIONS #
##################
def convert_dcm_to_nii():
    """Convert subject DICOM folders to gzipped NIfTI files.

    Role:
        Walks each subject directory in the study folder, detects a DICOM-containing
        subfolder, and runs dcm2niix when NIfTI outputs are not already present.

    Inputs:
        None (uses global path_to_study).

    Outputs:
        Writes .nii.gz files into each subject folder as a side effect.
        Returns nothing.
    """
    data_root = Path(path_to_study)
    
    ## check if dcm2niix completed, and if not, run it and gzip files
    for subject_folder in data_root.iterdir():
        if not subject_folder.is_dir():
            continue

        # Skip if NIfTI files already exist
        if any(subject_folder.glob("*.nii*")):
            print(f"{subject_folder.name}: NIfTI already exists, skipping.")
            continue

        # Find subfolder containing DICOM files
        dcm_subfolder = None
        for subfolder in subject_folder.iterdir():
            if subfolder.is_dir() and any(is_dicom(f) for f in subfolder.iterdir() if f.is_file()):
                dcm_subfolder = subfolder
                break

        if dcm_subfolder is None:
            print(f"{subject_folder.name}: No DICOM files found, skipping.")
            continue

        # Run dcm2niix
        print(f"{subject_folder.name}: Converting DICOMs in {dcm_subfolder.name}...")
        cmd = 'dcm2niix -z y -o %s %s' % (
            str(subject_folder), str(dcm_subfolder)
        )
        run_cmd(cmd)

def rename_files(subject, file_starting_name='2026', name_start_length=0, rename=False):
    """Preview or apply filename prefix normalization for one subject.

    Role:
        Finds files whose initial prefix matches file_starting_name and rewrites
        them to begin with the subject identifier.

    Inputs:
        subject (str): Subject folder name.
        file_starting_name (str): Prefix expected in raw filenames.
        name_start_length (int): Number of leading characters to replace.
        rename (bool): If False, only prints source/destination pairs.

    Outputs:
        Renamed files on disk when rename=True.
        Returns nothing.
    """
    path_to_subject = '%s/%s' % (path_to_study, subject)
    filenames = os.listdir(path_to_subject)
    for filename in filenames:
        path_to_file = '%s/%s' % (path_to_subject, filename)
        if os.path.isdir(path_to_file):
            continue
        elif os.path.isfile(path_to_file):
            name_start = filename[0:name_start_length]
            if file_starting_name in name_start:
                original_filepath = '%s/%s' % (path_to_subject, filename)
                destination_filepath = '%s/%s_%s' % (path_to_subject, subject, filename[name_start_length:])
                print(original_filepath)
                print(destination_filepath)
                print("##############")
                if rename == True:
                    if not os.path.exists(destination_filepath):
                        os.rename(original_filepath, destination_filepath)

def duplicate_and_rename_files(subject, overwrite=False):
    """Standardize sequence filenames and archive non-analysis files.

    Role:
        Performs subject-level file housekeeping: gzip conversion, archive moves,
        and sequence-specific renaming for MP2RAGE, T2star, B1 map, DWI, and MT/T1W.

    Inputs:
        subject (str): Subject folder name.
        overwrite (bool): Reserved parameter (not currently used in logic).

    Outputs:
        Renamed/moved files in the subject folder and archive subfolder.
        Returns nothing.
    """
    new_filepaths = []

    path_to_subject = '%s/%s' % (path_to_study, subject)
    subject_folder = Path(path_to_subject)
    archive_folder = subject_folder / 'archive'
    archive_folder.mkdir(exist_ok=True)

    for file in os.listdir(path_to_subject):
        if file.endswith('nii'):
            file_nii_gz = '%s/%s.gz' % (path_to_subject, file)
            # if the .gz exist, delete the .nii
            if os.path.isfile(file_nii_gz):
                run_cmd('rm %s/%s' % (path_to_subject, file))
            # if the .gz does not exist, gzip the .nii file
            else:
                run_cmd('gzip %s/%s' % (path_to_subject, file))

    # Matches _ROI1.nii.gz OR numbers 100, 100a, 101, 101a, etc. at the end before extension
    archive_pattern = re.compile(r'(_ROI1\.nii\.gz|1\d{2}a?(\.json|\.nii\.gz)?)$')

    # Loop through all files in the subject folder
    for file in subject_folder.iterdir():
        if file.is_file() and archive_pattern.search(file.name):
            dest = archive_folder / file.name
            print(f"Archiving {file.name} -> {dest}")
            shutil.move(str(file), str(dest))

    for file in os.listdir(path_to_subject):
        original_filepath = '%s/%s' % (path_to_subject, file)

        if os.path.isdir(original_filepath):
            pass
        elif file.startswith('%s_localizer' % subject):
            destination_filepath = '%s/archive/%s' % (path_to_subject, file)
            shutil.move(original_filepath, destination_filepath)
        
        ## MP2RAGE
        elif file.startswith('%s_%s' % (subject, mp2rage_file_start)):
            # if ends with .bval or .bvec, move to archive
            if file.endswith('.bval') or file.endswith('.bvec'):
                destination_filepath = '%s/archive/%s' % (path_to_subject, file)
                shutil.move(original_filepath, destination_filepath)
            
            elif file.endswith('.json'):
                with open(original_filepath, 'r') as f:
                    data = json.load(f)
                    value = data.get('SeriesDescription', None)

                    destination_filepath_json = '%s/%s_%s.json' % (path_to_subject, subject, value)
                    original_filepath_niigz = original_filepath.split('.json')[0] + '.nii.gz'
                    destination_filepath_niigz = '%s/%s_%s.nii.gz' % (path_to_subject, subject, value)

                    if original_filepath != destination_filepath_json:
                        if not os.path.exists(destination_filepath_json):
                            os.rename(original_filepath, destination_filepath_json)
                        
                        if not os.path.exists(destination_filepath_niigz):
                            os.rename(original_filepath_niigz, destination_filepath_niigz)

        ## T2star
        elif file.startswith(f"{subject}_{t2star_file_start}"):
            # Regex pattern to remove the 1–2 digit number before optional _e#, _ph, and extension
            # Captures everything before the number, keeps _e# and _ph if present, keeps extension
            
            # Pattern to match endings
            ending_pattern = re.compile(r'_e\d+(_ph)?(\.nii\.gz|\.json)$')
            if not ending_pattern.search(file):
                print(file) 
                if file.endswith('.json'):
                    with open(original_filepath, 'r') as f:
                        data = json.load(f)
                        value = data.get('SeriesDescription', None)
                        destination_filepath_json = '%s/%s_%s.json' % (path_to_subject, subject, value)
                        original_filepath_niigz = original_filepath.split('.json')[0] + '.nii.gz'
                        destination_filepath_niigz = '%s/%s_%s.nii.gz' % (path_to_subject, subject, value)

                        if original_filepath != destination_filepath_json:
                            if not os.path.exists(destination_filepath_json):
                                os.rename(original_filepath, destination_filepath_json)
                            
                            if not os.path.exists(destination_filepath_niigz):
                                os.rename(original_filepath_niigz, destination_filepath_niigz)
            else:

                pattern = re.compile(
                    r'^(.*)_(\d{1,2})(_e\d+)?(_ph)?(\.nii\.gz|\.json)$'
                )
                m = pattern.match(file)
                if m:
                    # Build new name without the number
                    new_name = f"{m.group(1)}{m.group(3) or ''}{m.group(4) or ''}{m.group(5)}"
                    new_path = '%s/%s' % (path_to_subject, new_name)

                if not os.path.exists(new_path):
                    os.rename(original_filepath, new_path)

        elif file.startswith('%s_%s' % (subject, b1map_file_start)):
            if file.endswith('.json'):

                if ('anatomical' in file) or ('flip_angle_map' in file):
                    continue

                with open(original_filepath, 'r') as f:
                    print(original_filepath)
                    data = json.load(f)
                    value = data.get('ImageComments', None)
                    original_filepath_niigz = original_filepath.split('.json')[0] + '.nii.gz'

                    if 'anatomical' in value:
                        destination_filepath_json = '%s/%s_%s_anatomical.json' % (path_to_subject, subject, b1map_file_start)
                        destination_filepath_niigz = '%s/%s_%s_anatomical.nii.gz' % (path_to_subject, subject, b1map_file_start)

                    elif 'flip angle map' in value:
                        destination_filepath_json = '%s/%s_%s_flip_angle_map.json' % (path_to_subject, subject, b1map_file_start)
                        destination_filepath_niigz = '%s/%s_%s_flip_angle_map.nii.gz' % (path_to_subject, subject, b1map_file_start)

                    if not os.path.exists(destination_filepath_json):
                        os.rename(original_filepath, destination_filepath_json)
                    if not os.path.exists(destination_filepath_niigz):
                        os.rename(original_filepath_niigz, destination_filepath_niigz)

        elif (dwi_b0_pa_file_start in file) or (dwi_38dir_ap_file_start in file) or (dwi_70dir_ap_file_start in file):
            
            if file.endswith('.json'):
                with open(original_filepath, 'r') as f:
                    data = json.load(f)
                    value = data.get('SeriesDescription', None)

                    new_path_json = '%s/%s_%s.json' % (path_to_subject, subject, value)
                    os.rename(original_filepath, new_path_json)

                    file_endings = ['nii.gz', 'bvec', 'bval']
                    for file_ending in file_endings:
                        original_path_ending = original_filepath.split('.')[0] + '.' + file_ending
                        new_path_ending = '%s/%s_%s.%s' % (path_to_subject, subject, value, file_ending)
                        if os.path.exists(original_path_ending):
                            os.rename(original_path_ending, new_path_ending)

        elif (mton_file_start in file) or (mtoff_file_start in file) or (t1w_file_start in file):
            if mton_file_start in file:
                filestart = mton_file_start
            elif mtoff_file_start in file:
                filestart = mtoff_file_start
            elif t1w_file_start in file:
                filestart = t1w_file_start
            
            if file.endswith('.json'):
                original_filepath_niigz = original_filepath.split('.json')[0] + '.nii.gz'

                if file.endswith('ph.json'):
                    new_filepath_json = '%s/%s_%s_ph.json' % (path_to_subject, subject, filestart)
                    new_filepath_niigz = '%s/%s_%s_ph.nii.gz' % (path_to_subject, subject, filestart)
                else:
                    new_filepath_json = '%s/%s_%s.json' % (path_to_subject, subject, filestart)
                    new_filepath_niigz = '%s/%s_%s.nii.gz' % (path_to_subject, subject, filestart)
            
                if not os.path.exists(new_filepath_json):
                    os.rename(original_filepath, new_filepath_json)
                if not os.path.exists(new_filepath_niigz):
                    os.rename(original_filepath_niigz, new_filepath_niigz)

def _get_phase_encoding_line(json_path):
    """Build one FSL acqparams line from a DWI sidecar JSON.

    Role:
        Parses phase-encoding direction and readout timing metadata and converts
        them to the FSL acqparams format used by topup/eddy.

    Inputs:
        json_path (str): Path to DWI JSON sidecar.

    Outputs:
        str: One acqparams line, for example "0 -1 0 0.052".
        Raises ValueError if required metadata is missing/unsupported.
    """
    with open(json_path, 'r') as f:
        data = json.load(f)

    pe_direction = data.get('PhaseEncodingDirection', None)
    if pe_direction is None:
        raise ValueError('Missing PhaseEncodingDirection in %s' % json_path)

    if 'BandwidthPerPixelPhaseEncode' in data:
        readout = float(round(1 / data['BandwidthPerPixelPhaseEncode'], 4))
    elif 'TotalReadoutTime' in data:
        readout = float(data['TotalReadoutTime'])
    else:
        raise ValueError('Missing BandwidthPerPixelPhaseEncode/TotalReadoutTime in %s' % json_path)

    if pe_direction == 'i':
        return '1 0 0 %s' % readout
    if pe_direction == 'i-':
        return '-1 0 0 %s' % readout
    if pe_direction == 'j':
        return '0 1 0 %s' % readout
    if pe_direction == 'j-':
        return '0 -1 0 %s' % readout
    if pe_direction == 'k':
        return '0 0 1 %s' % readout
    if pe_direction == 'k-':
        return '0 0 -1 %s' % readout

    raise ValueError('Unsupported PhaseEncodingDirection (%s) in %s' % (pe_direction, json_path))


def _load_bvals(bval_file):
    """Load a bval file as a 1D float array.

    Role:
        Normalizes b-value loading so downstream code can assume consistent shape.

    Inputs:
        bval_file (str): Path to .bval file.

    Outputs:
        numpy.ndarray: 1D float array of b-values.
    """
    return np.atleast_1d(np.loadtxt(bval_file)).astype(float)


def _load_bvecs(bvec_file, n_vols):
    """Load and validate bvecs in 3 x N orientation.

    Role:
        Reads bvec values, fixes common transposed layouts, and validates expected
        dimension compatibility with the number of DWI volumes.

    Inputs:
        bvec_file (str): Path to .bvec file.
        n_vols (int): Expected number of gradient directions/volumes.

    Outputs:
        numpy.ndarray: Array shaped (3, n_vols).
        Raises ValueError on incompatible shape.
    """
    bvecs = np.loadtxt(bvec_file)
    bvecs = np.atleast_2d(bvecs)

    if bvecs.shape[0] != 3 and bvecs.shape[1] == 3:
        bvecs = bvecs.T

    if bvecs.shape[0] != 3 and bvecs.size == n_vols * 3:
        bvecs = np.reshape(bvecs, (3, n_vols))

    if bvecs.shape[0] != 3 or bvecs.shape[1] != n_vols:
        raise ValueError('Unexpected bvec shape %s in %s (expected 3x%s)' % (bvecs.shape, bvec_file, n_vols))

    return bvecs


def _discover_raw_dwi_series(path_to_subject):
    """Discover RAW DWI AP/PA shell series and required sidecars.

    Role:
        Scans a subject folder for files matching *_RAW_DWI_b<shell>[ _PA ].nii.gz
        and records matching .nii.gz/.bval/.bvec/.json bundles.

    Inputs:
        path_to_subject (str): Subject directory path.

    Outputs:
        dict: Nested mapping {"AP": {shell: paths}, "PA": {shell: paths}}.
    """
    series_pattern = re.compile(r'^(?P<prefix>.+_RAW_DWI_b(?P<bval>\d+))(?P<pa>_PA)?\.nii\.gz$')
    series = {'AP': {}, 'PA': {}}

    for filename in os.listdir(path_to_subject):
        m = series_pattern.match(filename)
        if not m:
            continue

        prefix = m.group('prefix')
        phase = 'PA' if m.group('pa') else 'AP'
        bval_num = int(m.group('bval'))

        nii = '%s/%s' % (path_to_subject, filename)
        bval = '%s/%s.bval' % (path_to_subject, prefix + ('_PA' if phase == 'PA' else ''))
        bvec = '%s/%s.bvec' % (path_to_subject, prefix + ('_PA' if phase == 'PA' else ''))
        jsn = '%s/%s.json' % (path_to_subject, prefix + ('_PA' if phase == 'PA' else ''))

        if not (os.path.exists(bval) and os.path.exists(bvec) and os.path.exists(jsn)):
            continue

        series[phase][bval_num] = {
            'nii': nii,
            'bval': bval,
            'bvec': bvec,
            'json': jsn,
        }

    return series


def process_dwi(subject, overwrite=False, n_cores=18):
    """Run DWI preprocessing, diffusion metrics, and AMICO modeling.

    Role:
        Executes the end-to-end DWI workflow for one subject: AP/PA discovery,
        topup/applytopup, AP shell merge, bval/bvec merge, denoise, degibbs,
        eddy, DTI metric maps, AMICO NODDI outputs, and derived AWF/ECVF maps.

    Inputs:
        subject (str): Subject folder name.
        overwrite (bool): Recompute selected outputs when True.
        n_cores (int): Thread count passed to MRtrix commands.

    Outputs:
        Multiple NIfTI/text outputs in the subject folder (intermediate and final).
        Returns nothing.
    """
    # will run denoising and de-gibbs ringing before eddy
    path_to_subject = '%s/%s' % (path_to_study, subject)

    raw_series = _discover_raw_dwi_series(path_to_subject)
    if len(raw_series['AP']) == 0:
        print('No AP RAW DWI series found for subject %s' % subject)
        return

    shared_shells = sorted(set(raw_series['AP'].keys()).intersection(set(raw_series['PA'].keys())))
    if len(shared_shells) == 0:
        raise RuntimeError('No matched AP/PA RAW DWI shells found for subject %s' % subject)

    reference_shell = shared_shells[0]
    ap_reference = raw_series['AP'][reference_shell]
    pa_reference = raw_series['PA'][reference_shell]

    ap_file = '%s/AP.nii.gz' % path_to_subject
    pa_file = '%s/PA.nii.gz' % path_to_subject
    ap_pa_file = '%s/AP_PA.nii.gz' % path_to_subject

    if not os.path.exists(ap_file):
        cmd = 'fslroi %s %s/AP.nii.gz 0 1' % (ap_reference['nii'], path_to_subject)
        run_cmd(cmd)

    if not os.path.exists(pa_file):
        cmd = 'fslroi %s %s/PA.nii.gz 0 1' % (pa_reference['nii'], path_to_subject)
        run_cmd(cmd)

    if not os.path.exists(ap_pa_file):
        cmd = 'fslmerge -t %s %s %s' % (ap_pa_file, ap_file, pa_file)
        run_cmd(cmd)

    # set the acq_param.txt file from matched AP/PA pair
    acq_params_txt = '%s/acq_param.txt' % path_to_subject
    acq = _get_phase_encoding_line(ap_reference['json']) + '\n' + _get_phase_encoding_line(pa_reference['json'])
    with open(acq_params_txt, 'w') as file1:
        file1.write(acq)

    imain = ap_pa_file
    datain = acq_params_txt
    config = 'b02b0.cnf' # default file in FSL's libraries, will be automatically detected
    out = '%s/AP_PA_topup' % path_to_subject

    cmd = 'topup --imain=%s --datain=%s --config=%s --out=%s' % (
        imain, datain, config, out
    )

    ap_pa_topup_fieldcoef = '%s/AP_PA_topup_fieldcoef.nii.gz' % path_to_subject
    if not os.path.exists(ap_pa_topup_fieldcoef):
        run_cmd(cmd)

    # combine all AP RAW DWI shells (e.g., b300/b700/b2500)
    ap_shells = sorted(raw_series['AP'].keys())
    dwi_38dir_70dir = '%s/dwi_AP_combined.nii.gz' % path_to_subject
    ap_nii_files = [raw_series['AP'][shell]['nii'] for shell in ap_shells]
    cmd = 'fslmerge -t %s %s' % (dwi_38dir_70dir, ' '.join(ap_nii_files))
    if not os.path.exists(dwi_38dir_70dir):
        run_cmd(cmd)

    # combine shell bvals and bvecs in shell order
    dwi_38dir_70dir_bvals = '%s/dwi_AP_combined.bval' % path_to_subject
    dwi_38dir_70dir_bvecs = '%s/dwi_AP_combined.bvec' % path_to_subject

    merged_bvals = []
    merged_bvecs = []
    for shell in ap_shells:
        shell_bvals = _load_bvals(raw_series['AP'][shell]['bval'])
        shell_bvecs = _load_bvecs(raw_series['AP'][shell]['bvec'], len(shell_bvals))
        merged_bvals.append(shell_bvals)
        merged_bvecs.append(shell_bvecs)

    merged_bvals = np.concatenate(merged_bvals)
    merged_bvecs = np.concatenate(merged_bvecs, axis=1)

    if not os.path.exists(dwi_38dir_70dir_bvals):
        np.savetxt(dwi_38dir_70dir_bvals, merged_bvals[np.newaxis, :], fmt='%.8g')

    if not os.path.exists(dwi_38dir_70dir_bvecs):
        np.savetxt(dwi_38dir_70dir_bvecs, merged_bvecs, fmt='%.8f')

    # apply topup
    imain = dwi_38dir_70dir
    datain = acq_params_txt
    topup = '%s/AP_PA_topup' % path_to_subject
    out = '%s/AP_Cor' % path_to_subject

    cmd = 'applytopup --imain=%s --inindex=1 --datain=%s --topup=%s --method=jac --out=%s' % (
        imain, datain, topup, out
    )

    ap_cor = '%s/AP_Cor.nii.gz' % path_to_subject
    if not os.path.exists(ap_cor):
        print(cmd)
        run_cmd(cmd)

    # make the brain mask
    ap_1stvol = '%s/AP_1stVol.nii.gz' % path_to_subject
    cmd = 'fslroi %s %s 0 1' % (ap_cor, ap_1stvol)
    if not os.path.exists(ap_1stvol):
        run_cmd(cmd)

    ap_brain = '%s/AP_brain' % path_to_subject
    ap_brain_mask = '%s_mask.nii.gz' % ap_brain
    cmd = 'bet %s %s -m -f 0.2' % (ap_1stvol, ap_brain)
    if not os.path.exists(ap_brain_mask):
        run_cmd(cmd)

    # create index with one entry per DWI volume
    len_index = nib.load(dwi_38dir_70dir).shape[3]
    with open('%s/index.txt' % path_to_subject, 'w') as file:
        index_to_write = '1 ' * len_index
        file.write(index_to_write.strip())

    # run denoising
    dwi_38dir_70dir_denoised = '%s/dwi_AP_combined_denoised.nii.gz' % path_to_subject
    if not os.path.exists(dwi_38dir_70dir_denoised):
        cmd = 'dwidenoise %s %s -nthreads %s' % (dwi_38dir_70dir, dwi_38dir_70dir_denoised, n_cores)
        print(cmd)
        run_cmd(cmd)

    # run gibbs deringing on denoised image
    dwi_38dir_70dir_denoised_degibbs = '%s/dwi_AP_combined_denoised_degibbs.nii.gz' % path_to_subject
    if not os.path.exists(dwi_38dir_70dir_denoised_degibbs):
        cmd = 'mrdegibbs %s %s -nthreads %s' % (dwi_38dir_70dir_denoised, dwi_38dir_70dir_denoised_degibbs, n_cores)
        print(cmd)
        run_cmd(cmd)

    # create the brain mask from the denoised degibbs image
    dwi_38dir_70dir_denoised_degibbs_1stVol = '%s/dwi_AP_combined_denoised_degibbs_1stVol.nii.gz' % path_to_subject
    cmd = 'fslroi %s %s 0 1' % (dwi_38dir_70dir_denoised_degibbs, dwi_38dir_70dir_denoised_degibbs_1stVol)
    if not os.path.exists(dwi_38dir_70dir_denoised_degibbs_1stVol):
        print(cmd)
        run_cmd(cmd)

    dwi_38dir_70dir_denoised_degibbs_1stVol_brain = '%s/dwi_AP_combined_denoised_degibbs_1stVol_brain' % path_to_subject
    cmd = 'bet %s %s -m -f 0.1' % (dwi_38dir_70dir_denoised_degibbs_1stVol, dwi_38dir_70dir_denoised_degibbs_1stVol_brain)
    if not os.path.exists(dwi_38dir_70dir_denoised_degibbs_1stVol_brain + '_mask.nii.gz'):
        print(cmd)
        run_cmd(cmd)

    # run eddy
    imain = dwi_38dir_70dir_denoised_degibbs
    mask = dwi_38dir_70dir_denoised_degibbs_1stVol_brain + '_mask.nii.gz'
    index = '%s/index.txt' % path_to_subject
    acqp = acq_params_txt
    bvecs = dwi_38dir_70dir_bvecs
    bvals = dwi_38dir_70dir_bvals
    topup = '%s/AP_PA_topup' % path_to_subject
    out = '%s/AP_eddy_unwarped_denoised_degibbs' % path_to_subject

    cmd = 'eddy --imain=%s --mask=%s --index=%s --acqp=%s --bvecs=%s --bvals=%s --fwhm=0 --topup=%s --flm=quadratic --out=%s --data_is_shelled --very_verbose' % (
        imain, mask, index, acqp, bvecs, bvals, topup, out
    )

    ap_eddy_unwarped_denoised_degibbs = '%s/AP_eddy_unwarped_denoised_degibbs.nii.gz' % path_to_subject
    if not os.path.exists(ap_eddy_unwarped_denoised_degibbs):
        print(cmd)
        run_cmd(cmd)

    # INITIALIZE AND FIT DT and KT OBJECTS
            
    # run DTI        
    final_files = [os.path.exists('%s/%s_dti_fa_rgb_dipy.nii.gz' % (path_to_subject, subject)),
                    os.path.exists(('%s/%s_dti_fa_dipy.nii.gz' % (path_to_subject, subject))),
                    os.path.exists(('%s/%s_dti_md_dipy.nii.gz' % (path_to_subject, subject))),
                    os.path.exists(('%s/%s_dti_ad_dipy.nii.gz' % (path_to_subject, subject))),
                    os.path.exists(('%s/%s_dti_rd_dipy.nii.gz' % (path_to_subject, subject))),
                    ]
    if all(final_files) and not overwrite:
        print('DTI parameters already completed for subject %s' % subject)
    else:
        print('Starting DTI parameters for subject %s' % subject)

        # set up gradient table
        b_val = np.loadtxt(dwi_38dir_70dir_bvals) 
        b_vec = np.loadtxt(dwi_38dir_70dir_bvecs)
        b_vec = np.reshape(b_vec, (3, len(b_val)))
        grad_tab = gradient_table(b_val, b_vec)

        # load data from previous step
        img_dat_denoised = (nib.load(ap_eddy_unwarped_denoised_degibbs)).get_fdata()
        binary_mask = (nib.load(dwi_38dir_70dir_denoised_degibbs_1stVol_brain + '_mask.nii.gz')).get_fdata()
        img_affine = (nib.load(ap_eddy_unwarped_denoised_degibbs)).affine

        dti_model = dti.TensorModel(grad_tab)
        dti_fit = dti_model.fit(img_dat_denoised, mask=binary_mask)
        dti_FA = dti_fit.fa  # fractional anistropy
        dti_MD = dti_fit.md  # mean diffusivity
        dti_AD = dti_fit.ad  # axial diffusivity
        dti_RD = dti_fit.rd  # radial diffusivity

        # colourize the FA
        dti_FA[np.isnan(dti_FA)] = 0
        dti_FA = np.clip(dti_FA, 0, 1)
        dti_FA_RGB = color_fa(dti_FA, dti_fit.evecs)
        save_nifti('%s/%s_dti_fa_rgb_dipy.nii.gz' % (path_to_subject, subject),
                np.array(255 * dti_FA_RGB, 'uint8'),
                img_affine)
        save_nifti('%s/%s_dti_fa_dipy.nii.gz' % (path_to_subject, subject),
                dti_FA.astype(np.single),
                img_affine)
        save_nifti('%s/%s_dti_md_dipy.nii.gz' % (path_to_subject, subject),
                dti_MD.astype(np.single),
                img_affine)
        save_nifti('%s/%s_dti_ad_dipy.nii.gz' % (path_to_subject, subject),
                dti_AD.astype(np.single),
                img_affine)
        save_nifti('%s/%s_dti_rd_dipy.nii.gz' % (path_to_subject, subject),
                dti_RD.astype(np.single),
                img_affine)
        
    # run AMICO
    # AMICO tutorial: https://qmrlab.readthedocs.io/en/latest/amico_batch.html#3
    # AMICO paper: https://www.sciencedirect.com/science/article/pii/S0165027020303319#sec0030
    amico.core.setup()

    # generate a scheme file from the .bval and .bvec files
    # check if the scheme file exists
    scheme = '%s/dwi_AP_combined.scheme' % (path_to_subject)

    dwi_preprocessed_file = '%s/AP_eddy_unwarped_denoised_degibbs.nii.gz' % path_to_subject
    bvals_file = '%s/dwi_AP_combined.bval' % path_to_subject
    bvecs_file = '%s/dwi_AP_combined.bvec' % path_to_subject
    mask_filename = dwi_38dir_70dir_denoised_degibbs_1stVol_brain + '_mask.nii.gz'

    # if the file does not exist, run the function
    # if bStep is a scalar, round b-values to the nearest integer multiple of bStep
    if not os.path.isfile(scheme):
        amico.util.fsl2scheme(bvals_file,
                                bvecs_file,
                                scheme,
                                bStep=50
                                )
    # if all the files exist, then skip, otherwise run
    final_files = [os.path.exists('%s/AMICO/NODDI/%s_config.pickle' % (path_to_subject, subject)),
                    os.path.exists('%s/AMICO/NODDI/%s_fit_dir.nii.gz' % (path_to_subject, subject)),
                    os.path.exists('%s/AMICO/NODDI/%s_fit_NDI.nii.gz' % (path_to_subject, subject)),
                    os.path.exists('%s/AMICO/NODDI/%s_fit_FWF.nii.gz' % (path_to_subject, subject)),
                    os.path.exists('%s/AMICO/NODDI/%s_fit_ODI.nii.gz' % (path_to_subject, subject)),
                    ]
    if all(final_files) and not overwrite:
        print('AMICO already completed for subject %s' % subject)
    else:
        print('Starting AMICO for subject %s' % subject)

        # tell AMICO the location/directory containing all the data for this study/subject and load the corresponding file
        ae = amico.Evaluation(path_to_study, path_to_subject)

        ae.load_data(dwi_preprocessed_file,
                         scheme,
                         mask_filename,
                         b0_thr=50,
                         ) # Vlad used b0_thr=0, but my data has 20 for the b=0 images in the bval file
        # set model for NODDI
        ae.set_model('NODDI')

        # using default model parameters because MS is a clinical example in the original paper
        # if you want to change them, use the following and replace the ? symbols
        """
        ae.model.set(
            dPar= ?,
            dIso= ?,
        )
        """
        # Generate the response functions for all the compartments
        # Scheme files with the same b-values but different number/distribution of samples on each shell will result in the same precomputed kernels
        # You need to compute the response functions only once per study.
        ae.generate_kernels(regenerate=True)  # The default flag is regenerate = False

        # load the precomputed kernels and adapt them to the actual scheme (distribution of points on each shell) of the current subject
        ae.load_kernels()

        # Model Fit. May take some time depending on the number of voxels
        ae.fit()

        # Save the results as NifTI images:
        ae.save_results()

        path_to_noddi = '%s/AMICO/NODDI' % (path_to_subject)

        # rename the files so that they have the subject name at the start
        files = os.listdir(path_to_noddi)
        for file in files:
            # for files, not directories
            if os.path.isfile('%s/%s' % (path_to_noddi, file)):
                # print('%s/%s' % (path_to_noddi, file))
                if not file.startswith(subject):
                    new_file = '%s_%s' % (subject, file)
                    os.rename('%s/%s' % (path_to_noddi, file), '%s/%s' % (path_to_noddi, new_file))

    ## create AWF
    # AWF = ICVF * (1-ISOVF)
    # AWF = (ISOVF*(-1) + 1) * ICVF
    iso = '%s/AMICO/NODDI/%s_fit_FWF.nii.gz' % (path_to_subject, subject)
    ic = '%s/AMICO/NODDI/%s_fit_NDI.nii.gz' % (path_to_subject, subject)
    awf = '%s/%s_AWF.nii.gz' % (path_to_subject, subject)

    cmd = 'fslmaths %s -mul -1 -add 1 -mul %s %s' % (iso, ic, awf)

    if not os.path.exists(awf) or overwrite:
        print('Creating AWF for subject %s' % subject)
        run_cmd(cmd)
    else:
        print('AWF already created for subject %s' % subject)

    # ECVF = 1 - ICVF
    # ECVF = ICVF*(-1) + 1
    ecvf = '%s/%s_ECVF.nii.gz' % (path_to_subject, subject)

    cmd = 'fslmaths %s -mul -1 -add 1 %s' % (ic, ecvf)

    if not os.path.exists(ecvf) or overwrite:
        print('Creating ECVF for subject %s' % subject)
        run_cmd(cmd)
    else:
        print('ECVF already created for subject %s' % subject)

####################
# HELPER FUNCTIONS #
####################
def run_cmd(sys_cmd, outputs=False):
    """Execute a shell command and capture stdout/stderr.

    Role:
        Central command runner used by preprocessing steps for external tools.

    Inputs:
        sys_cmd (str): Shell command string to execute.
        outputs (bool): If True, print stdout in addition to stderr.

    Outputs:
        tuple[bytes, bytes]: (stdout, stderr) from the subprocess.
    """
    print(sys_cmd)
    p = subprocess.Popen(sys_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
    stdout, stderr = p.communicate()
    print(stderr)
    if outputs:
        print(stdout)
    return stdout, stderr

def is_dicom(file_path):
    """Check if a file is a DICOM by reading the magic number at byte 128."""
    try:
        with open(file_path, 'rb') as f:
            f.seek(128)
            magic = f.read(4)
            return magic == b'DICM'
    except:
        return False
    
def shutil_copy_overwrite(original, new, overwrite=False):
    """Copy an image file and its paired JSON sidecar.

    Role:
        Helper to copy a file while optionally overwriting and mirroring its
        sidecar metadata file when present.

    Inputs:
        original (str): Source image path.
        new (str): Destination image path.
        overwrite (bool): If True, overwrite existing destination.

    Outputs:
        Copies files on disk as side effects.
        Returns nothing.
    """
    
    if not os.path.exists(original):
        print('%s does not exist' % original)
        exit()
    if not os.path.exists(new) or overwrite:
        shutil.copy(original, new)

    original_json = original.split('.')[0] + '.json'
    new_json = new.split('.')[0] + '.json'

    if os.path.exists(original_json):
        if not original_json == new_json:
            shutil.copy(original_json, new_json)


##################
# FUNCTION CALLS #
##################
# convert_dcm_to_nii()

file_starting_names = {
    '20260313': 'Test_Hannah_Test_Hannah',
    'MS_DG_074': None,
    '20251014': 'Test_Hannah',
}

name_start_lengths = {
    '20260313': 43,
    'MS_DG_074': None,
    '20251014': 31,
}

# file_starting_name = 'Test_Hannah_Test_Hannah' # can change to the year in future
n_cores = 18

subjects = ['20260313', 'MS_DG_074', '20251014', ]
for subject in subjects:
    file_starting_name = file_starting_names[subject]
    name_start_length = name_start_lengths[subject]

    if file_starting_name != None:
        rename_files(subject, file_starting_name, name_start_length, rename=False)
        ### confirm that the new naming convention works
        rename_files(subject, file_starting_name, name_start_length, rename=True)
        pass
    duplicate_and_rename_files(subject) ## add PC-MRI, FLAIR, DCE
    process_dwi(subject, overwrite=False, n_cores=n_cores)
    pass