# Azure Scheduled Jobs Scaffold

This folder is intentionally isolated from the trading code and generated result folders. It contains the Azure deployment wrapper for the existing Windows scheduled jobs:

| Local task | IST schedule | UTC cron | Azure job name |
| --- | ---: | ---: | --- |
| `TB11_Phase1_QuoteObservation_0940` | 09:40 Mon-Fri | `10 4 * * 1-5` | `tb11-phase1-0940` |
| `TB11_T28_ChainBandFreshness_0945` | 09:45 Mon-Fri | `15 4 * * 1-5` | `tb11-t28-0945` |
| `TB11_Phase1_QuoteObservation_1230` | 12:30 Mon-Fri | `0 7 * * 1-5` | `tb11-phase1-1230` |
| `TB11_Phase1_QuoteObservation_1445` | 14:45 Mon-Fri | `15 9 * * 1-5` | `tb11-phase1-1445` |

Azure Container Apps scheduled job cron expressions are UTC. India does not use daylight saving time, so the conversion is stable.

## What This Runs

The wrapper in `scripts/run_tb11_job.sh` mirrors the current `.bat` files:

- `phase1`: `signal_baseline_tb11_options_phase1_auto_quote_observation` -> Phase 2 readiness -> transition controller.
- `t28`: `signal_baseline_tb11_options_nifty_chain_band_quote_collector` -> T28 freshness gate -> Phase 2 readiness -> transition controller.

The repo-level Python code is not modified by this scaffold.

## Prerequisites

- Azure CLI installed and logged in with `az login`.
- A target Azure subscription selected with `az account set --subscription "<subscription-id>"`.
- Docker available locally, or use Azure Container Registry build.
- Zerodha/Kite secrets available as Azure Container Apps job secrets.

## Details Needed Before First Deploy

1. `subscriptionId`
2. `resourceGroup`
3. `location` such as `centralindia` or `southindia`
4. globally unique ACR name
5. Container Apps environment name
6. Log Analytics workspace name
7. storage account name and file share name for persisted `data/`, `results/`, and logs
8. Zerodha/Kite secret names and values
9. GitHub token or deploy key only if the jobs should push generated artifacts back to GitHub
10. alert target for failures, such as email, Teams webhook, or Azure Monitor action group

## Build Locally

From the repo root:

```powershell
docker build -f azure_scheduled_jobs/Dockerfile -t ctrade1-tb11-jobs:local .
```

Smoke test a no-order run locally:

```powershell
docker run --rm --env SSELL1_NONINTERACTIVE=1 ctrade1-tb11-jobs:local phase1
```

## Deploy

The deployment helper is parameterized and does not assume your subscription details:

```powershell
.\azure_scheduled_jobs\scripts\deploy_container_jobs.ps1 `
  -SubscriptionId "<subscription-id>" `
  -ResourceGroup "rg-ctrade1-jobs" `
  -Location "centralindia" `
  -AcrName "<globally-unique-acr-name>" `
  -EnvironmentName "cae-ctrade1-jobs" `
  -LogAnalyticsName "law-ctrade1-jobs" `
  -StorageAccountName "<globallyuniquestorage>" `
  -FileShareName "ctrade1state"
```

After deployment, run the manual smoke job first:

```powershell
az containerapp job start --name tb11-phase1-0940 --resource-group rg-ctrade1-jobs
```

Check execution history and logs:

```powershell
az containerapp job execution list --name tb11-phase1-0940 --resource-group rg-ctrade1-jobs --output table
az containerapp job logs show --name tb11-phase1-0940 --resource-group rg-ctrade1-jobs --follow
```

## Operational Notes

- Broker orders remain blocked by the existing `ssell1.py` controls; this scaffold does not enable live orders.
- Persisted output should be mounted at `/app/results` and `/app/data` through Azure Files before relying on the jobs operationally.
- If the storage mount is not configured, Container Apps job filesystem writes are ephemeral.
- NSE holiday skipping should stay inside the Python gate or be added as a small guard before calling `ssell1.py`.
