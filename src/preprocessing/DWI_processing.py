import time
start = time.time()
import subprocess
import os
import numpy as np
import nibabel as nib
from dipy.io.image import save_nifti
from dipy.core.gradients import gradient_table
import dipy.reconst.dti as dti
from dipy.reconst.dti import color_fa
import json
import re
from pathlib import Path


path_to_data = '/export01/data'
study = 'Ethan-COMP-401'
subjects = ['HC_AM_071_15-11-23_3T']
path_to_study = '%s/%s' % (path_to_data, study)

def _get_subject_directory(subject):
	"""Return the absolute subject directory path."""
	return os.path.expanduser('%s/%s' % (path_to_study, subject))


def _get_dwi_directory(subject):
	"""Resolve the directory containing a subject's RAW DWI series.

	Supports both of these layouts:
	1. <study>/<subject>/*.nii.gz
	2. <study>/<subject>/DWI/*.nii.gz
	"""
	subject_dir = _get_subject_directory(subject)
	candidate_dirs = [subject_dir, '%s/DWI' % subject_dir]

	for candidate in candidate_dirs:
		if os.path.isdir(candidate):
			series = _discover_raw_dwi_series(candidate)
			if len(series['AP']) > 0 or len(series['PA']) > 0:
				return candidate

	for candidate in candidate_dirs:
		if os.path.isdir(candidate):
			return candidate

	raise FileNotFoundError('Could not find subject or DWI directory for %s' % subject)


def _resolve_fsl_config(config_name):
	"""Resolve an FSL config file name to a concrete path."""
	if os.path.isabs(config_name) and os.path.exists(config_name):
		return config_name

	search_paths = [os.getcwd()]
	fsldir = os.environ.get('FSLDIR')
	if fsldir:
		search_paths.append(os.path.join(fsldir, 'etc', 'flirtsch'))

	search_paths.extend([
		'/usr/local/fsl/etc/flirtsch',
		'/opt/fsl/etc/flirtsch',
		'/usr/share/fsl/etc/flirtsch',
		'/usr/share/fsl/5.0/etc/flirtsch',
	])

	for directory in search_paths:
		candidate = os.path.join(directory, config_name)
		if os.path.exists(candidate):
			return candidate

	raise FileNotFoundError(
		'Could not locate FSL config file %s. Set FSLDIR or pass an absolute config path.' % config_name
	)


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

def _get_phase_encoding_line(json_path):
	"""Build one FSL acqparams line from a DWI sidecar JSON."""
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
	"""Load a bval file as a 1D float array."""
	return np.atleast_1d(np.loadtxt(bval_file)).astype(float)


def _load_bvecs(bvec_file, n_vols):
	"""Load and validate bvecs in 3 x N orientation."""
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
	"""Discover RAW DWI AP/PA shell series and required sidecars."""
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


def process_dwi_until_dti(subject, overwrite=False, n_cores=18):
	"""Run DWI preprocessing through DTI metric map generation only."""
	path_to_subject = _get_dwi_directory(subject)

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
	config = _resolve_fsl_config('b02b0.cnf')
	out = '%s/AP_PA_topup' % path_to_subject

	cmd = 'topup --imain=%s --datain=%s --config=%s --out=%s' % (
		imain, datain, config, out
	)

	ap_pa_topup_fieldcoef = '%s/AP_PA_topup_fieldcoef.nii.gz' % path_to_subject
	if not os.path.exists(ap_pa_topup_fieldcoef):
		run_cmd(cmd)

	# combine all AP RAW DWI shells (e.g., b300/b700/b2500)
	ap_shells = sorted(raw_series['AP'].keys())
	combined_dwi_ap_shells = '%s/dwi_AP_combined.nii.gz' % path_to_subject
	ap_nii_files = [raw_series['AP'][shell]['nii'] for shell in ap_shells]
	cmd = 'fslmerge -t %s %s' % (combined_dwi_ap_shells, ' '.join(ap_nii_files))
	if not os.path.exists(combined_dwi_ap_shells):
		run_cmd(cmd)

	# combine shell bvals and bvecs in shell order
	combined_dwi_bvals = '%s/dwi_AP_combined.bval' % path_to_subject
	combined_dwi_bvecs = '%s/dwi_AP_combined.bvec' % path_to_subject

	merged_bvals = []
	merged_bvecs = []
	for shell in ap_shells:
		shell_bvals = _load_bvals(raw_series['AP'][shell]['bval'])
		shell_bvecs = _load_bvecs(raw_series['AP'][shell]['bvec'], len(shell_bvals))
		merged_bvals.append(shell_bvals)
		merged_bvecs.append(shell_bvecs)

	merged_bvals = np.concatenate(merged_bvals)
	merged_bvecs = np.concatenate(merged_bvecs, axis=1)

	if not os.path.exists(combined_dwi_bvals):
		np.savetxt(combined_dwi_bvals, merged_bvals[np.newaxis, :], fmt='%.8g')

	if not os.path.exists(combined_dwi_bvecs):
		np.savetxt(combined_dwi_bvecs, merged_bvecs, fmt='%.8f')

	# apply topup
	imain = combined_dwi_ap_shells
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
	len_index = nib.load(combined_dwi_ap_shells).shape[3]
	with open('%s/index.txt' % path_to_subject, 'w') as file:
		index_to_write = '1 ' * len_index
		file.write(index_to_write.strip())

	# run denoising
	combined_dwi_denoised = '%s/dwi_AP_combined_denoised.nii.gz' % path_to_subject
	if not os.path.exists(combined_dwi_denoised):
		cmd = 'dwidenoise %s %s -nthreads %s' % (combined_dwi_ap_shells, combined_dwi_denoised, n_cores)
		print(cmd)
		run_cmd(cmd)

	# run gibbs deringing on denoised image
	combined_dwi_denoised_degibbs = '%s/dwi_AP_combined_denoised_degibbs.nii.gz' % path_to_subject
	if not os.path.exists(combined_dwi_denoised_degibbs):
		cmd = 'mrdegibbs %s %s -nthreads %s' % (combined_dwi_denoised, combined_dwi_denoised_degibbs, n_cores)
		print(cmd)
		run_cmd(cmd)

	# create the brain mask from the denoised degibbs image
	combined_dwi_denoised_degibbs_1stVol = '%s/dwi_AP_combined_denoised_degibbs_1stVol.nii.gz' % path_to_subject
	cmd = 'fslroi %s %s 0 1' % (combined_dwi_denoised_degibbs, combined_dwi_denoised_degibbs_1stVol)
	if not os.path.exists(combined_dwi_denoised_degibbs_1stVol):
		print(cmd)
		run_cmd(cmd)

	combined_dwi_denoised_degibbs_1stVol_brain = '%s/dwi_AP_combined_denoised_degibbs_1stVol_brain' % path_to_subject
	cmd = 'bet %s %s -m -f 0.1' % (combined_dwi_denoised_degibbs_1stVol, combined_dwi_denoised_degibbs_1stVol_brain)
	if not os.path.exists(combined_dwi_denoised_degibbs_1stVol_brain + '_mask.nii.gz'):
		print(cmd)
		run_cmd(cmd)

	# run eddy
	imain = combined_dwi_denoised_degibbs
	mask = combined_dwi_denoised_degibbs_1stVol_brain + '_mask.nii.gz'
	index = '%s/index.txt' % path_to_subject
	acqp = acq_params_txt
	bvecs = combined_dwi_bvecs
	bvals = combined_dwi_bvals
	topup = '%s/AP_PA_topup' % path_to_subject
	out = '%s/AP_eddy_unwarped_denoised_degibbs' % path_to_subject

	cmd = 'eddy --imain=%s --mask=%s --index=%s --acqp=%s --bvecs=%s --bvals=%s --fwhm=0 --topup=%s --flm=quadratic --out=%s --data_is_shelled --very_verbose' % (
		imain, mask, index, acqp, bvecs, bvals, topup, out
	)

	ap_eddy_unwarped_denoised_degibbs = '%s/AP_eddy_unwarped_denoised_degibbs.nii.gz' % path_to_subject
	if not os.path.exists(ap_eddy_unwarped_denoised_degibbs):
		print(cmd)
		run_cmd(cmd)

	# run DTI
	final_files = [
		os.path.exists('%s/%s_dti_fa_rgb_dipy.nii.gz' % (path_to_subject, subject)),
		os.path.exists('%s/%s_dti_fa_dipy.nii.gz' % (path_to_subject, subject)),
		os.path.exists('%s/%s_dti_md_dipy.nii.gz' % (path_to_subject, subject)),
		os.path.exists('%s/%s_dti_ad_dipy.nii.gz' % (path_to_subject, subject)),
		os.path.exists('%s/%s_dti_rd_dipy.nii.gz' % (path_to_subject, subject)),
	]

	if all(final_files) and not overwrite:
		print('DTI parameters already completed for subject %s' % subject)
	else:
		print('Starting DTI parameters for subject %s' % subject)

		b_val = np.loadtxt(combined_dwi_bvals)
		b_vec = np.loadtxt(combined_dwi_bvecs)
		b_vec = np.reshape(b_vec, (3, len(b_val)))
		grad_tab = gradient_table(b_val, b_vec)

		img_dat_denoised = (nib.load(ap_eddy_unwarped_denoised_degibbs)).get_fdata()
		binary_mask = (nib.load(combined_dwi_denoised_degibbs_1stVol_brain + '_mask.nii.gz')).get_fdata()
		img_affine = (nib.load(ap_eddy_unwarped_denoised_degibbs)).affine

		dti_model = dti.TensorModel(grad_tab)
		dti_fit = dti_model.fit(img_dat_denoised, mask=binary_mask)
		dti_FA = dti_fit.fa
		dti_MD = dti_fit.md
		dti_AD = dti_fit.ad
		dti_RD = dti_fit.rd

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


def run_cmd(sys_cmd, outputs=False):
	"""Execute a shell command and capture stdout/stderr."""
	print(sys_cmd)
	completed = subprocess.run(
		sys_cmd,
		stdout=subprocess.PIPE,
		stderr=subprocess.PIPE,
		shell=True,
		text=True,
		errors='replace'
	)
	if completed.stderr:
		print(completed.stderr)
	if outputs and completed.stdout:
		print(completed.stdout)
	if completed.returncode != 0:
		raise RuntimeError(
			'Command failed with exit code %s: %s\n%s' % (
				completed.returncode,
				sys_cmd,
				completed.stderr.strip() or completed.stdout.strip()
			)
		)
	return completed.stdout, completed.stderr

def is_dicom(file_path):
    """Check if a file is a DICOM by reading the magic number at byte 128."""
    try:
        with open(file_path, 'rb') as f:
            f.seek(128)
            magic = f.read(4)
            return magic == b'DICM'
    except:
        return False


if __name__ == '__main__':
	n_cores = 18
	for subject in subjects:
		process_dwi_until_dti(subject, overwrite=False, n_cores=n_cores)

