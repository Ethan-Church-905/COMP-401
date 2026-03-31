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

def process_dwi(subject, overwrite=False, n_cores=18):
    # will run denoising and de-gibbs ringing before eddy
    path_to_subject = '%s/%s' % (path_to_study, subject)
    # take the first volume of the dwi_38_nii as the AP b=0
    ap_file = '%s/AP.nii.gz' % path_to_subject
    pa_file = '%s/PA.nii.gz' % path_to_subject
    ap_pa_file = '%s/AP_PA.nii.gz' % path_to_subject

    dwi_b0_PA_nii = '%s/%s_%s.nii.gz' % (path_to_subject, subject, dwi_b0_pa_file_start)
    dwi_b0_PA_json = '%s/%s_%s.json' % (path_to_subject, subject, dwi_b0_pa_file_start)
    
    dwi_38_nii = '%s/%s_%s.nii.gz' % (path_to_subject, subject, dwi_38dir_ap_file_start)
    dwi_38_json = '%s/%s_%s.json' % (path_to_subject, subject, dwi_38dir_ap_file_start)
    dwi_38_bval = '%s/%s_%s.bval' % (path_to_subject, subject, dwi_38dir_ap_file_start)
    dwi_38_bvec = '%s/%s_%s.bvec' % (path_to_subject, subject, dwi_38dir_ap_file_start)

    dwi_70_nii = '%s/%s_%s.nii.gz' % (path_to_subject, subject, dwi_70dir_ap_file_start)
    dwi_70_json = '%s/%s_%s.json' % (path_to_subject, subject, dwi_70dir_ap_file_start)
    dwi_70_bval = '%s/%s_%s.bval' % (path_to_subject, subject, dwi_70dir_ap_file_start)
    dwi_70_bvec = '%s/%s_%s.bvec' % (path_to_subject, subject, dwi_70dir_ap_file_start)


    if not os.path.exists(ap_file):        
        cmd = 'fslroi %s %s/AP.nii.gz 0 1' % (dwi_38_nii, path_to_subject)
        run_cmd(cmd)

    if not os.path.exists(pa_file):
        cmd = 'fslroi %s %s/PA.nii.gz 0 1' % (dwi_b0_PA_nii, path_to_subject)
        run_cmd(cmd)

    if not os.path.exists(ap_pa_file):
        cmd = 'fslmerge -t %s %s %s' % (ap_pa_file, ap_file, pa_file)
        run_cmd(cmd)

    # set the acq_param.txt file
    b0_json1 = dwi_38_json
    f = open(b0_json1, 'r')
    b0_data1 = json.loads(f.read())
    pe_1 = b0_data1['PhaseEncodingDirection']
    bw_pp_pe_1 = b0_data1['BandwidthPerPixelPhaseEncode']
    pe_bw_pp_1 = str(round(1/bw_pp_pe_1, 4))

    b0_json2 = dwi_b0_PA_json
    f = open(b0_json2, 'r')
    b0_data2 = json.loads(f.read())
    pe_2 = b0_data2['PhaseEncodingDirection']
    bw_pp_pe_2 = b0_data2['BandwidthPerPixelPhaseEncode']
    pe_bw_pp_2 = str(round(1/bw_pp_pe_2, 4))

    acq = ''
    if pe_1 == 'j':
            acq += '0 1 0 %s\n' % pe_bw_pp_1
    elif pe_1 == 'j-':
        acq += '0 -1 0 %s\n' % pe_bw_pp_1

    if pe_2 == 'j':
        acq += '0 1 0 %s' % pe_bw_pp_2
    elif pe_2 == 'j-':
        acq += '0 -1 0 %s' % pe_bw_pp_2

    acq_params_txt = '%s/acq_param.txt' % path_to_subject

    file1 = open(acq_params_txt, 'w')
    file1.write(acq)
    file1.close()

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

    # combine the dwi38dir and dwi70dir
    dwi_38dir_70dir = '%s/dwi_38dir_70dir.nii.gz' % (path_to_subject)
    cmd = 'fslmerge -t %s %s %s' % (dwi_38dir_70dir, dwi_38_nii, dwi_70_nii)
    if not os.path.exists(dwi_38dir_70dir):
        run_cmd(cmd)

    # combine their bvals
    f1 = open(dwi_38_bval, 'r')
    f1_vals = ((f1.readlines())[0]).split('\n')[0]
    f1.close()
    f2 = open(dwi_70_bval, 'r')
    f2_vals = ((f2.readlines())[0]).split('\n')[0]
    f2.close()

    dwi_38dir_70dir_bvals = '%s/dwi_38dir_70dir.bval' % path_to_subject
    if not os.path.exists(dwi_38dir_70dir_bvals):
        file = open(dwi_38dir_70dir_bvals, 'w')
        file.writelines('%s %s' % (f1_vals, f2_vals))
        file.close()
    
    # combine their bvecs
    f1 = open(dwi_38_bvec, 'r')
    f1_vals = f1.readlines()
    dwi_38_bvec_0 = (((f1_vals[0]).split('\n')[0]).split(' '))
    dwi_38_bvec_1 = (((f1_vals[1]).split('\n')[0]).split(' '))
    dwi_38_bvec_2 = (((f1_vals[2]).split('\n')[0]).split(' '))
    f1.close()
    f2 = open(dwi_70_bvec, 'r')
    f2_vals = f2.readlines()
    dwi_70_bvec_0 = (((f2_vals[0]).split('\n')[0]).split(' '))
    dwi_70_bvec_1 = (((f2_vals[1]).split('\n')[0]).split(' '))
    dwi_70_bvec_2 = (((f2_vals[2]).split('\n')[0]).split(' '))
    f2.close()

    # they are all lists
    new_vec = ''
    for i in dwi_38_bvec_0:
        new_vec = new_vec + i + ' '
    for i in dwi_70_bvec_0:
        new_vec = new_vec + i + ' '
    new_vec = new_vec + '\n'

    for i in dwi_38_bvec_1:
        new_vec = new_vec + i + ' '
    for i in dwi_70_bvec_1:
        new_vec = new_vec + i + ' '
    new_vec = new_vec + '\n'

    for i in dwi_38_bvec_2:
        new_vec = new_vec + i + ' '
    for i in dwi_70_bvec_2:
        new_vec = new_vec + i + ' '

    dwi_38dir_70dir_bvecs = '%s/dwi_38dir_70dir.bvec' % path_to_subject
    if not os.path.exists(dwi_38dir_70dir_bvecs):
        file = open(dwi_38dir_70dir_bvecs, 'w')
        file.writelines(new_vec)
        file.close()
        
    # apply topup
    imain = dwi_38dir_70dir
    datain = acq_params_txt
    topup = '%s/AP_PA_topup' % path_to_subject
    out = '%s/AP_Cor' % path_to_subject

    cmd = 'applytopup --imain=%s --inindex=1 --datain=%s --topup=%s --method=jac --out=%s' % (
        imain, datain, topup, out
    )
    
    ap_cor = '%s/AP_Cor.nii.gz' % (path_to_subject)
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

    # create index with 110 repeats of 1
    len_index = 110
    file = open('%s/index.txt' % path_to_subject, 'w')
    index_to_write = '1 ' * len_index
    index_to_write = index_to_write[:-1]
    file.write(index_to_write)
    file.close()

    # run denoising
    dwi_38dir_70dir_denoised = '%s/dwi_38dir_70dir_denoised.nii.gz' % path_to_subject
    if not os.path.exists(dwi_38dir_70dir_denoised):
        cmd = 'dwidenoise %s %s -nthreads %s' % (dwi_38dir_70dir, dwi_38dir_70dir_denoised, n_cores)
        print(cmd)
        run_cmd(cmd)

    # run gibbs deringing on denoised image
    dwi_38dir_70dir_denoised_degibbs = '%s/dwi_38dir_70dir_denoised_degibbs.nii.gz' % path_to_subject
    if not os.path.exists(dwi_38dir_70dir_denoised_degibbs):
        cmd = 'mrdegibbs %s %s -nthreads %s' % (dwi_38dir_70dir_denoised, dwi_38dir_70dir_denoised_degibbs, n_cores)
        print(cmd)
        run_cmd(cmd)

    # create the brain mask from the denoised degibbs image
    dwi_38dir_70dir_denoised_degibbs_1stVol = '%s/dwi_38dir_70dir_denoised_degibbs_1stVol.nii.gz' % path_to_subject
    cmd = 'fslroi %s %s 0 1' % (dwi_38dir_70dir_denoised_degibbs, dwi_38dir_70dir_denoised_degibbs_1stVol)
    if not os.path.exists(dwi_38dir_70dir_denoised_degibbs_1stVol):
        print(cmd)
        run_cmd(cmd)

    dwi_38dir_70dir_denoised_degibbs_1stVol_brain = '%s/dwi_38dir_70dir_denoised_degibbs_1stVol_brain' % path_to_subject
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
    scheme = '%s/dwi_38dir_70dir.scheme' % (path_to_subject)

    dwi_preprocessed_file = '%s/AP_eddy_unwarped_denoised_degibbs.nii.gz' % path_to_subject
    bvals_file = '%s/dwi_38dir_70dir.bval' % path_to_subject
    bvecs_file = '%s/dwi_38dir_70dir.bvec' % path_to_subject
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