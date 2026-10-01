# IMPULSE Kaggle Free GPU Execution Environment

This directory provides provider-neutral bootstrap and execution scripts for running IMPULSE experiments on Kaggle notebook sessions (T4x2 or P100).

## Governance & Safety Rules
1. **Zero Credentials:** Never commit or hardcode personal Kaggle API tokens (`kaggle.json`).
2. **Experiment Invariance:** The experiment configuration and prompts remain 100% invariant across environments.
3. **Evidence Separation:** Live external results must record their compute fingerprint and environment class (`KAGGLE_FREE_GPU`).
4. **Reproducibility:** All transferred artifacts are SHA-256 verified prior to execution.

## Execution Steps in Kaggle Notebook
1. Enable GPU accelerator (GPU T4x2 or P100) in Kaggle Notebook Settings.
2. Clone or unpack the verified IMPULSE repository snapshot.
3. Run the environment check:
   ```bash
   python compute/kaggle/environment_check.py
   ```
4. Execute the targeted experiment via preflight-verified runner:
   ```bash
   python compute/kaggle/run_experiment.py --experiment L1
   ```
