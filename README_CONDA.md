# Conda environment for this workspace

This repository includes a ready-to-use conda environment file.

Create the environment:
```bash
conda env create -f environment.yml
conda activate playground-env
```

If you prefer `mamba` (faster):
```bash
mamba env create -f environment.yml
mamba activate playground-env
```

Update the environment from changes in `environment.yml`:
```bash
conda env update -f environment.yml --prune
```

Export current environment to `environment.yml`:
```bash
conda env export > environment.yml
```

Notes:
- On macOS, install Miniconda or Mambaforge if you don't have conda.
- Adjust Python version or packages in `environment.yml` as needed.
