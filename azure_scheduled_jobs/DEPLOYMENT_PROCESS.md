# Azure Scheduled Jobs Deployment Process

This note documents how the TB11 scheduled jobs were packaged and deployed to Azure Container Apps jobs.

## What Is In `azure_scheduled_jobs`

- `Dockerfile`: builds the runtime image from `python:3.13-slim`, installs Linux tools and Python dependencies, copies the sanitized repo contents into `/app`, and sets `scripts/run_tb11_job.sh` as the container entrypoint.
- `Dockerfile.dockerignore`: excludes local secrets and generated folders if someone builds directly with Docker from the repo root.
- `requirements-azure.txt`: Python packages needed by the Azure runtime. This uses CPU-only Torch to keep the image smaller.
- `scripts/run_tb11_job.sh`: runtime wrapper executed inside the container. It runs the selected TB11 mode sequence, writes logs, prunes older per-run logs, and optionally pushes generated outputs back to GitHub.
- `scripts/deploy_container_jobs.ps1`: deployment automation. It builds a sanitized temporary build context, pushes an image through Azure Container Registry, creates or updates Azure resources, and recreates the four scheduled jobs.
- `infra/containerapp-job.template.yaml`: Container Apps job template. The deploy script fills in resource IDs, image, cron, secrets, env vars, managed identity, and Azure Files mounts.
- `README.md`: quick operator reference for schedules, deploy command, and operational notes.

## High-Level Deployment Flow

1. Start from the local repo on the workstation.

2. The deploy script reads required secrets from local `.env`:
   - `API_KEY`
   - `API_SECRET`
   - `USERNAME`
   - `PASSWORD`
   - `TOTP_KEY`
   - optional `GITHUB_TOKEN` or `GH_TOKEN`

3. The deploy script creates a sanitized temporary build folder under `%TEMP%`.

4. The sanitized build folder is populated from `git ls-files`, not from every file in the working directory.

5. The deploy script excludes generated or sensitive paths from the build context:
   - `.env`
   - `.env.example`
   - `access_token_cache.txt`
   - `optuna_study.db`
   - `data/`
   - `results*/`
   - `plots/`
   - `tensorboard_logs*/`

6. The current `azure_scheduled_jobs/` folder is copied into that sanitized context, so deployment wrapper changes are included even when the local repo has other unrelated generated files.

7. Azure Container Registry build is started against that sanitized context:
   - registry: `HeldC1`
   - image: `heldc1.azurecr.io/ctrade1/tb11-jobs:latest`
   - Dockerfile: `azure_scheduled_jobs/Dockerfile`

8. The Dockerfile installs system packages and Python dependencies, then copies the sanitized source tree into `/app`.

9. The repo is not cloned by the container to obtain runnable code. The runnable code is baked into the image at build time under `/app`.

10. Azure resources are created or updated:
    - resource group: `MyRG`
    - Container Apps environment: `cae-ctrade1-jobs`
    - Log Analytics workspace: `law-ctrade1-jobs`
    - storage account: `stctrade1ramic`
    - Azure Files shares:
      - `ctrade1stateresults` mounted at `/app/results`
      - `ctrade1statedata` mounted at `/app/data`

11. A user-assigned managed identity is used for ACR image pulls:
    - identity: `id-ctrade1-jobs`
    - role: `AcrPull` on `HeldC1`
    - ACR admin credentials are not enabled or used.

12. The deploy script renders `infra/containerapp-job.template.yaml` once per scheduled job and creates the jobs.

13. Existing jobs are deleted and recreated so the latest image, env vars, cron, secret references, and mounts are applied consistently.

14. The jobs run on UTC cron expressions that map to India market times:
    - `tb11-phase1-0940`: `10 4 * * 1-5`
    - `tb11-t28-0945`: `15 4 * * 1-5`
    - `tb11-phase1-1230`: `0 7 * * 1-5`
    - `tb11-phase1-1445`: `15 9 * * 1-5`

15. These schedules are weekday schedules, not full NSE holiday-aware schedules. A weekday exchange holiday would still start the container unless a separate holiday guard is added.

## Runtime Flow Inside The Container

1. Azure starts the Container Apps job according to the cron or a manual force run.

2. The container starts in `/app` and runs:

   ```bash
   /app/azure_scheduled_jobs/scripts/run_tb11_job.sh <job-kind>
   ```

3. The wrapper writes an Azure job log under:

   ```text
   /app/results/log_runs/tb11_<job-kind>_<UTC timestamp>_azure.log
   ```

4. For `phase1`, the wrapper runs these `ssell1.py` modes:
   - `signal_baseline_tb11_options_phase1_auto_quote_observation`
   - `signal_baseline_tb11_options_phase2_paper_price_reconciliation_readiness`
   - `signal_baseline_tb11_options_phase2_transition_controller`

5. For `t28`, the wrapper runs these `ssell1.py` modes:
   - `signal_baseline_tb11_options_nifty_chain_band_quote_collector`
   - `signal_baseline_tb11_options_t28_freshness_gate`
   - `signal_baseline_tb11_options_phase2_paper_price_reconciliation_readiness`
   - `signal_baseline_tb11_options_phase2_transition_controller`

6. The jobs write outputs into the mounted Azure Files paths:
   - `/app/results`
   - `/app/data`

7. Before pushing outputs to GitHub, the wrapper prunes old per-run logs:
   - keeps logs from the last `LOG_RETENTION_DAYS`, default `3`
   - preserves at least `LOG_RETENTION_MIN_FILES`, default `6`, per log pattern
   - targets `results/log_runs/run_*` and `results/log_runs/tb11_*_azure.log`

8. If GitHub output push is enabled, the wrapper clones the repo into a temporary directory:

   ```text
   /tmp/ctrade1-output-push
   ```

9. This runtime clone is only for committing generated outputs. It is not used to run the code.

10. The wrapper merges generated `results` and `data` files from `/app` into the temporary clone without deleting existing repo artifacts.

11. The wrapper commits changed outputs with message `Record Azure scheduled job outputs`.

12. The wrapper pushes the output commit to the configured branch, currently `main`.

## Secret Handling

- Secrets are read from local `.env` only during deployment.
- The rendered Container Apps YAML exists only as a temporary file under `%TEMP%` and is deleted after job creation.
- Azure stores the values as Container Apps job secrets.
- The container receives secret values through `secretRef` environment variables.
- The GitHub token is used as a transient Git HTTP auth header. It is not embedded in the Git remote URL.
- ACR pull authentication uses managed identity, not registry username/password.

## What Was Validated

- ACR build used a small sanitized upload context, around `329 KiB` in the observed deployment.
- Final image was pushed to `heldc1.azurecr.io/ctrade1/tb11-jobs:latest`.
- All four jobs were recreated with provisioning state `Succeeded`.
- Force runs succeeded for:
  - `tb11-phase1-0940`
  - `tb11-t28-0945`
  - `tb11-phase1-1230`
  - `tb11-phase1-1445`
- The scheduled `tb11-phase1-0940` run started at `2026-07-06T04:10:00Z`, matching `09:40 IST`, and completed successfully.
- Log retention was deployed and validated with a force run that printed the pruning message before pushing outputs.
