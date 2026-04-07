"""
helper functions for the analysis of the thalamocortical tracts. This includes functions for loading and processing the tractography data, as well as functions for visualizing the results.
"""


import numpy as np
import nibabel as nib
from dipy.io.streamline import load_tck
from dipy.stats.analysis import afq_profile, gaussian_weights
from dipy.segment.clustering import QuickBundles
from dipy.segment.metric import AveragePointwiseEuclideanMetric
from dipy.segment.featurespeed import ResampleFeature
from dipy.tracking.streamline import orient_by_streamline

def load_nifti(file):
    '''
    Loads a nifti file and returns the data and affine.
    '''

    img = nib.load(file)
    return img.get_fdata(), img.affine



def load_tck_file(file):
    '''
    Loads a tck file and returns the streamlines.
    '''
    return load_tck(file).streamlines


def get_tract_profile(bundle, metric_img, metric_affine, use_weights=False, flip=True, num_points=100):
    '''
    This function reorients the streamlines and extracts the diffusion metrics along the tract.
    It essentially performs step 1 of viets sample_along_tract script. The default number of points is 100
    which can be thought of as %-along a tract. The flip variable signals if you would like to flip the direction of the streamlines after reorientation.
    For example if after reorientation all the streamlines were motor cortex -> brainstem and you actually wanted brainstem -> motor cortex, then you set flip to True. 
    The default is True because generally we see reorientation result in motor cortex -> brainstem. For the honours project, we were looking for the opposite.
    '''

    # Reorient all the streamlines so that they are following the same direction
    feature = ResampleFeature(nb_points=num_points)
    d_metric = AveragePointwiseEuclideanMetric(feature)
    qb = QuickBundles(np.inf, metric=d_metric)
    centroid_bundle = qb.cluster(bundle).centroids[0]
    oriented_bundle = orient_by_streamline(bundle, centroid_bundle)

    # Calculate weights for each streamline/node in a bundle, based on a Mahalanobis distance from the core the bundle, at that node
    w_bundle = None
    if use_weights:
        w_bundle = gaussian_weights(oriented_bundle)

    # Sample the metric along the tract. The implementation of this function is based off of work by Yeatman et al. in 2012
    profile_bundle = afq_profile(metric_img, oriented_bundle, metric_affine, weights=w_bundle)
    
    # Reverse the profile bundle if the direction is not desired
    if flip:
        profile_bundle = np.flip(profile_bundle)
    return profile_bundle


def get_tract_length(bundle):
    '''
    This function calculates the average length of the streamlines in a bundle.
    '''
    lengths = np.array([np.linalg.norm(s[-1] - s[0]) for s in bundle])
    return np.mean(lengths)