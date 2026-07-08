# Shared-Token Cutover Evidence - 2026-07-08

Objective: use one shared Kite access-token cache for TB11 options jobs and the equity L2 collector, with TOTP allowed only in the refresh-token job.

## Azure resources

- ACR: `HeldC1`
- Storage account: `stctrade1ramic`
- Shared token Azure Files share: `ctrade1-kite-token`
- Shared token Container Apps storage name: `ctrade1kitetoken`
- L2 data Azure Files share: `ctrade1-l2-data`
- Managed identity: `id-ctrade1-jobs`

## Image and deployment evidence

- Equity image built by remote ACR build: `heldc1.azurecr.io/ctrade1/equity-12-c011ector:shared-token`, digest `sha256:a003930959795938f5c51253e5c2f0de9285bfebf904d1a9c6e573ef945f5f27`.
- Options image rebuilt by remote ACR build after the temporary-file copy fix: `heldc1.azurecr.io/ctrade1/tb11-jobs-shared-token:latest`, digest `sha256:ca9810412375d75d68490b366e4e53cfa0a2d7f932bd5e98e39dc13c6a9a0ba9`.
- Four TB11 Container Apps jobs were redeployed on `tb11-jobs-shared-token:latest` with `/kite-token`, `KITE_TOKEN_CACHE_FILE=/kite-token/access_token_cache.txt`, and `KITE_ALLOW_TOTP_LOGIN=0`.

## Runtime proof

- Refresh Container Apps job execution `kite-token-refresh-73hizzm` succeeded on 2026-07-08. Logs showed the only intentional `TOTP login triggered` line and wrote `/kite-token/access_token_cache.txt` plus `access_token_cache.meta.json`.
- Forced TB11 consumer execution `tb11-phase1-1230-4az7xjj` succeeded with `[Cached] Logged in...`, `Totp_hits=0`, and `Invalid_cache_hits=0`.
- Equity ACI `l2-shared-token-live-20260708` used the same shared token cache, resolved 32 instruments, ran through market close, and terminated with exit code 0 at `2026-07-08T10:05:02Z`.
- Cross-workload overlap execution `tb11-phase1-1445-dph8vic` succeeded while the equity L2 ACI was live. Log Analytics counters: `cached_hits=1`, `totp_hits=0`, `token_errors=0`, `copy_errors=0`.

## L2 output audit

Targeted Azure Files audit of `ctrade1-l2-data` after the session:

- Symbol directories: 32
- Total Parquet files: 20,507
- Parquet files per symbol: min 640, max 641
- Zero-size files: 0
- Temporary files: 0
- Heartbeat rows: 146
- Max heartbeat gap: 3.78 minutes
- Last heartbeat: `2026-07-08T10:04:59.832547+00:00`
- Last heartbeat ticks since start: 226,430
- Token/disconnect/error markers in collector events: 0

## Follow-ups

- Keep equity L2 output on `ctrade1-l2-data`; do not mount it on the TB11 `/app/data` share.
- The TB11 output-push script now excludes `*.tmp` and `*.tmp.*` files as a defensive guard.
- Add alerts and an automated equity scheduler later; they were out of scope for this cutover.
