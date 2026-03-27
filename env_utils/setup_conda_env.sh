#!/bin/bash

# setup_conda_env.sh :: Create and configure the COMP-401 conda environment
# with all required Python packages for the along-tract analysis pipeline.

ENV_NAME="COMP-401"

echo "Creating conda environment: $ENV_NAME"

# Create conda environment with Python 3.9 (compatible with all packages)
conda create -n "$ENV_NAME" python=3.9 -y

# Activate the environment
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate "$ENV_NAME"

echo "Installing Python packages..."

# Install packages via conda where available (better dependency resolution)
conda install -y \
    numpy \
    scipy \
    pandas \
    matplotlib \
    seaborn

# Install packages via pip (some neuroimaging packages are better installed via pip)
pip install \
    "dipy>=1.1.1" \
    "nibabel>=3.1" \
    "nipype>=1.5" \
    compress-pickle

echo ""
echo "================================================"
echo "Conda environment '$ENV_NAME' created successfully!"
echo ""
echo "To activate the environment, run:"
echo "    conda activate $ENV_NAME"
echo "================================================"
