#!/bin/bash
# LUMI-C CPU job: final training + test forecast (LightGBM, ~minutes). NOT YET TESTED ON LUMI.
# Fill in the project id (find it with `lumi-workspaces`) before submitting: sbatch scripts/train_cpu.sbatch
#SBATCH --job-name=imbalance-final
#SBATCH --account=project_XXXXXXXXX
#SBATCH --partition=small
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=16G
#SBATCH --time=00:30:00
#SBATCH --output=outputs/slurm-%j.out

set -euo pipefail
cd "${SLURM_SUBMIT_DIR}"
# uv must be installed in your LUMI home (curl -LsSf https://astral.sh/uv/install.sh | sh), or load a python module
export OMP_NUM_THREADS=${SLURM_CPUS_PER_TASK}
uv sync --frozen
uv run scripts/run_final.py
