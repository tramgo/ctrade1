# Azure L2 Collector Deployment

This runbook packages and deploys the `zerodha_equity_collector` L2 shakedown workload to Azure Container Instances, following `l2xollectionplan_az1.txt`.

Defaults used by the scripts:

- ACR: `HeldC1`
- Image repository: `zerodha-12-c011ector`
- Resource group: `rg-12-c011ector-shakedown-cin`
- Region: `centralindia`
- Storage account: `st12c011ectorramic`
- Blob container: `raw-12`
- File share: `12-session`
- Managed identity: `id-12-c011ector`
- Key Vault: `kv-12-c011ector-ramic`

The deployment intentionally uses ACI and not Container Apps, AKS, App Service, Functions, VNets, inbound ports, Blob archive tiering, or IaC modules during phase one.

The resource group is always created separately from existing production/dev groups. It is tagged `workload=12-c011ector`, `phase=shakedown`, and `owner=expiry-2027-12-31` so rollback, cost attribution, RBAC scope, and lifecycle timing stay isolated from longer-lived resources.

The ACR is reused as a shared platform resource. The collector image is pushed to repository `zerodha-12-c011ector`, and the new managed identity receives `AcrPull` scoped to the existing registry.

The default storage path creates a new dedicated StorageV2 account in the shakedown resource group. Reusing an existing account is allowed only with `-ReuseStorageAccount`, and the setup script enforces these gates: location is Central India or South India, kind is StorageV2, firewall default action is not `Deny`, and no existing lifecycle policy is present. If reuse is deliberately chosen, RBAC is scoped to the blob container and file share, and the lifecycle rule filters only the `raw-12/`, `heartbeat/`, `audit/`, and `collector_events/` prefixes.

## Image

The Docker image is built from [Dockerfile](Dockerfile). It runs:

```bash
python -m zerodha_equity_collector.azure_entrypoint
```

The image does not include credentials, `.env` files, cached access tokens, or local runtime data. Secrets are read at container startup from Key Vault using the user-assigned managed identity.

The build context is the `zerodha_equity_collector` folder, not the full repo. This keeps ACR remote builds small and avoids uploading unrelated research artifacts.

## Key Vault Secrets

Populate these before the first ACI run:

- `kite-api-key`
- `kite-api-secret`
- `kite-username`
- `kite-password`
- `kite-totp-key`
- `access-token` optional, useful when a pre-generated token is available

The entrypoint exports them as `KITE_*` environment variables for the existing auth code. Access-token cache writes are redirected to `/data/access_token_cache.txt` on the Azure Files mount.

## Deploy Order

Run from the repo root.

1. Create or verify the resource shell:

```powershell
.\zerodha_equity_collector\scripts\setup_l2_azure_resources.ps1 `
  -AcrName HeldC1 `
  -StorageAccountName st12c011ectorramic
```

To reuse `stctrade1ramic` instead of creating a dedicated account, run with `-StorageAccountName stctrade1ramic -ReuseStorageAccount`. The script will stop if any reuse gate fails.

2. Populate Key Vault secrets manually.

```powershell
az keyvault secret set --vault-name kv-12-c011ector-ramic --name kite-api-key --value "..."
az keyvault secret set --vault-name kv-12-c011ector-ramic --name kite-api-secret --value "..."
az keyvault secret set --vault-name kv-12-c011ector-ramic --name kite-username --value "..."
az keyvault secret set --vault-name kv-12-c011ector-ramic --name kite-password --value "..."
az keyvault secret set --vault-name kv-12-c011ector-ramic --name kite-totp-key --value "..."
```

3. Build and push a pinned image tag:

```powershell
$tag = Get-Date -Format "yyyyMMdd-HHmmss"
.\zerodha_equity_collector\scripts\build_push_l2_image.ps1 `
  -AcrName HeldC1 `
  -Tag $tag `
  -UseAcrBuild
```

`-UseAcrBuild` builds inside Azure Container Registry and does not require the local Docker Desktop Linux engine. Omit it only when local Docker Linux is healthy.

4. Run the manual ACI proof during market hours:

```powershell
.\zerodha_equity_collector\scripts\run_l2_manual_aci.ps1 `
  -AcrName HeldC1 `
  -StorageAccountName st12c011ectorramic `
  -ImageTag $tag `
  -CollectorMode l2-live
```

For a short non-market smoke run, use `-CollectorMode l2-preflight`. For an intentional outside-session live connection test, add `-AllowOutsideSession`.

5. Inspect the container:

```powershell
az container logs --resource-group rg-12-c011ector-shakedown-cin --name 12-c011ector-manual
az container show --resource-group rg-12-c011ector-shakedown-cin --name 12-c011ector-manual --query instanceView.state
```

6. Verify Blob output:

```powershell
az storage blob list `
  --account-name st12c011ectorramic `
  --container-name raw-12 `
  --prefix raw-12/ `
  --auth-mode login `
  --num-results 20 `
  --output table
```

## Daily ACI Modes

The same image supports these `COLLECTOR_MODE` values:

- `l2-live`: market-session guarded collector, self-terminates at `15:35` IST
- `l2-audit`: runs `l2-audit`, `l2-shakedown-report`, `l2-plan-status`, and `l2-status`
- `l2-preflight`: connectivity and instrument-resolution checks
- `l2-status`: current local status summary

The manual ACI script sets these environment variables:

- `KEY_VAULT_NAME`
- `COLLECTOR_MODE`
- `COLLECTOR_DATA_ROOT=/data`
- `AZURE_STORAGE_ACCOUNT_URL=https://st12c011ectorramic.blob.core.windows.net`
- `AZURE_STORAGE_CONTAINER=raw-12`
- `AZURE_BLOB_PREFIX=` empty, because upload maps local `raw_l2/` to Blob `raw-12/`
- `AZURE_UPLOAD_AFTER_RUN=1`

## Scheduling

After the manual ACI proof is clean, create two Logic App Consumption workflows:

- Weekday `09:05` IST: create ACI with `COLLECTOR_MODE=l2-live`, pinned image tag, restart policy `Never`
- Weekday `15:50` IST: create ACI with `COLLECTOR_MODE=l2-audit`, same pinned image tag, restart policy `Never`

Do not reference `latest` in scheduled workflows. Use the pinned datetime tag produced by `build_push_l2_image.ps1`.

Set Logic App run-history retention to 30 days.

## Verified Shakedown Deployment

Verified on 2026-07-07:

- Resource group `rg-12-c011ector-shakedown-cin` exists in `centralindia` with tags `workload=12-c011ector`, `phase=shakedown`, and `owner=expiry-2027-12-31`.
- Dedicated storage account `st12c011ectorramic` exists in the shakedown resource group with Blob container `raw-12` and File share `12-session`.
- Existing ACR `HeldC1` contains repository `zerodha-12-c011ector` with pinned tag `20260707-203418` and `latest`.
- The pinned image digest used by ACI was `sha256:997cc80ba52090000fecbc1fa21ba52021fbaffde63f201152d809fa72730997`.
- Manual ACI smoke run `12-c011ector-manual` completed `l2-status` with exit code `0` and uploaded `audit/l2_status.csv` to Blob.
- Manual ACI preflight run `12-c011ector-preflight` completed `l2-preflight` with exit code `0`, validated the Kite profile, resolved `32` instruments, sampled quotes for `4` NSE symbols, and uploaded `audit/l2_preflight.csv`, `audit/resolved_instruments.csv`, and `audit/unresolved_instruments.csv`.

The 30-minute `l2-live` Parquet proof still needs to be run during Indian market hours. The July 7 verification was after market close, so `l2-preflight` was the correct non-market proof.

## Alerts

Only two alerts are intended for phase one:

- Collector did not run today on a non-holiday weekday.
- Daily audit reports `suspect_symbol_days > 0`.

Do not alert on individual disconnects or reconnects; those are captured in `collector_events` and rolled up by the audit.

## Cleanup

If a kill switch fires, delete the disposable workload resource group:

```powershell
az group delete --name rg-12-c011ector-shakedown-cin --yes --no-wait
```

The existing ACR is outside this cleanup path and is not deleted.
