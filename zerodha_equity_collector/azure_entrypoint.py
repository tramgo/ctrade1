from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


SECRET_ENV_MAP = {
    "kite-api-key": "KITE_API_KEY",
    "kite-api-secret": "KITE_API_SECRET",
    "kite-username": "KITE_USERNAME",
    "kite-password": "KITE_PASSWORD",
    "kite-totp-key": "KITE_TOTP_KEY",
}

MODE_COMMANDS = {
    "l2-live": ["l2-live"],
    "l2-audit": ["l2-audit", "l2-shakedown-report", "l2-plan-status", "l2-status"],
    "l2-preflight": ["l2-preflight"],
    "l2-status": ["l2-status"],
    "refresh-token": ["refresh-token"],
}


def require_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Set {name} before starting the Azure collector container.")
    return value


def fetch_key_vault_secrets() -> None:
    vault_name = os.getenv("KEY_VAULT_NAME", "").strip()
    if not vault_name:
        print("[azure-entrypoint] Key Vault skipped; KEY_VAULT_NAME not set", flush=True)
        return
    try:
        from azure.identity import DefaultAzureCredential
        from azure.keyvault.secrets import SecretClient
    except ImportError as exc:
        raise RuntimeError("Install azure-identity and azure-keyvault-secrets in the container image.") from exc

    client = SecretClient(
        vault_url=f"https://{vault_name}.vault.azure.net/",
        credential=DefaultAzureCredential(),
    )
    for secret_name, env_name in SECRET_ENV_MAP.items():
        if os.getenv(env_name):
            continue
        try:
            secret = client.get_secret(secret_name)
        except Exception:
            if secret_name == "access-token":
                continue
            raise
        if secret.value:
            os.environ[env_name] = secret.value
    if os.getenv("KITE_FETCH_KEYVAULT_ACCESS_TOKEN", "").strip().lower() in {"1", "true", "yes"}:
        try:
            secret = client.get_secret("access-token")
        except Exception:
            secret = None
        if secret is not None and secret.value and not os.getenv("KITE_ACCESS_TOKEN"):
            os.environ["KITE_ACCESS_TOKEN"] = secret.value


def run_collector_command(command: str) -> int:
    config = os.getenv(
        "COLLECTOR_CONFIG",
        "/app/zerodha_equity_collector/config/l2_collector_config.json",
    )
    args = [
        sys.executable,
        "-m",
        "zerodha_equity_collector.collector",
        "--config",
        config,
        command,
    ]
    if command == "l2-live" and os.getenv("ALLOW_OUTSIDE_SESSION", "").lower() in {"1", "true", "yes"}:
        args.append("--allow-outside-session")
    print(f"[azure-entrypoint] running {' '.join(args)}", flush=True)
    return subprocess.call(args)


def blob_name_for_local_file(relative_path: str, default_prefix: str) -> str:
    if relative_path.startswith("raw_l2/"):
        return "raw-12/" + relative_path[len("raw_l2/") :]
    if relative_path.startswith(("heartbeat/", "audit/", "collector_events/")):
        return relative_path
    return f"{default_prefix}/{relative_path}" if default_prefix else relative_path


def upload_data_to_blob() -> None:
    container = os.getenv("AZURE_STORAGE_CONTAINER", "").strip()
    account_url = os.getenv("AZURE_STORAGE_ACCOUNT_URL", "").strip()
    if not container or not account_url:
        print("[azure-entrypoint] blob upload skipped; AZURE_STORAGE_CONTAINER/account URL not set", flush=True)
        return

    data_root = Path(os.getenv("COLLECTOR_DATA_ROOT", "/data")).resolve()
    prefix = os.getenv("AZURE_BLOB_PREFIX", "").strip().strip("/")
    if not data_root.exists():
        print(f"[azure-entrypoint] blob upload skipped; data root missing: {data_root}", flush=True)
        return

    try:
        from azure.identity import DefaultAzureCredential
        from azure.storage.blob import BlobServiceClient, ContentSettings
    except ImportError as exc:
        raise RuntimeError("Install azure-identity and azure-storage-blob in the container image.") from exc

    service = BlobServiceClient(account_url=account_url, credential=DefaultAzureCredential())
    blob_container = service.get_container_client(container)
    skip_names = {"access_token_cache.txt"}
    skip_suffixes = {".tmp"}
    uploaded = 0
    for path in sorted(data_root.rglob("*")):
        if not path.is_file():
            continue
        if path.name in skip_names or path.suffix.lower() in skip_suffixes:
            continue
        relative = path.relative_to(data_root).as_posix()
        blob_name = blob_name_for_local_file(relative, prefix)
        content_type = "application/octet-stream"
        if path.suffix.lower() == ".csv":
            content_type = "text/csv"
        elif path.suffix.lower() == ".json":
            content_type = "application/json"
        elif path.suffix.lower() == ".jsonl":
            content_type = "application/x-ndjson"
        with path.open("rb") as handle:
            blob_container.upload_blob(
                name=blob_name,
                data=handle,
                overwrite=True,
                content_settings=ContentSettings(content_type=content_type),
            )
        uploaded += 1
        if os.getenv("AZURE_DELETE_AFTER_UPLOAD", "0").strip().lower() in {"1", "true", "yes"}:
            path.unlink()
    print(f"[azure-entrypoint] uploaded_files={uploaded} container={container} prefix={prefix}", flush=True)


def main() -> int:
    data_root = Path(os.getenv("COLLECTOR_DATA_ROOT", "/data"))
    data_root.mkdir(parents=True, exist_ok=True)
    token_dir = Path(os.getenv("KITE_TOKEN_CACHE_DIR", "/kite-token"))
    token_dir.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("KITE_TOKEN_CACHE_DIR", str(token_dir))
    os.environ.setdefault("KITE_TOKEN_CACHE_FILE", str(token_dir / "access_token_cache.txt"))
    os.environ.setdefault("KITE_ACCESS_TOKEN_CACHE", os.environ["KITE_TOKEN_CACHE_FILE"])
    os.environ.setdefault("KITE_ALLOW_TOTP_LOGIN", "0")
    os.environ.setdefault("ZERODHA_COLLECTOR_NONINTERACTIVE", "1")
    os.environ.setdefault("PYTHONUNBUFFERED", "1")

    fetch_key_vault_secrets()
    mode = (os.getenv("COLLECTOR_MODE") or (sys.argv[1] if len(sys.argv) > 1 else "l2-live")).strip().lower()
    commands = MODE_COMMANDS.get(mode)
    if not commands:
        raise RuntimeError(f"Unsupported COLLECTOR_MODE={mode}. Expected one of {sorted(MODE_COMMANDS)}")

    exit_code = 0
    for command in commands:
        exit_code = run_collector_command(command)
        if exit_code != 0:
            break

    if os.getenv("AZURE_UPLOAD_AFTER_RUN", "1").strip().lower() not in {"0", "false", "no"}:
        upload_data_to_blob()
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
