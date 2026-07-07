from __future__ import annotations

import os
import time
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import requests


MAX_RETRIES = 5
RETRY_DELAY_SECONDS = 10
MAX_RETRY_DELAY_SECONDS = 120


try:
    import truststore

    truststore.inject_into_ssl()
    TRUSTSTORE_STATUS = "windows_os_trust_enabled"
except ImportError:
    TRUSTSTORE_STATUS = "truststore_not_installed"
except Exception as exc:
    TRUSTSTORE_STATUS = f"truststore_injection_failed:{exc}"


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def load_local_env(env_path: Path) -> None:
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        # Match ssell1.py: local repo .env values intentionally override
        # ambient OS variables such as Windows USERNAME.
        if key:
            os.environ[key] = value


def load_default_env_files(config_dir: Path | None = None) -> None:
    candidates = []
    if config_dir is not None:
        candidates.append(config_dir / ".env")
    candidates.extend([Path(__file__).resolve().parent / ".env", repo_root() / ".env"])
    for path in candidates:
        load_local_env(path)


def get_api_key() -> str:
    api_key = os.getenv("KITE_API_KEY") or os.getenv("API_KEY")
    if not api_key:
        raise RuntimeError("Set KITE_API_KEY or API_KEY before running the collector.")
    return api_key.strip()


def get_api_secret() -> str:
    value = os.getenv("KITE_API_SECRET") or os.getenv("API_SECRET")
    if not value:
        raise RuntimeError("Set KITE_API_SECRET or API_SECRET for TOTP login fallback.")
    return value.strip()


def get_username() -> str:
    value = os.getenv("KITE_USERNAME") or os.getenv("USERNAME")
    if not value:
        raise RuntimeError("Set KITE_USERNAME or USERNAME for TOTP login fallback.")
    return value.strip()


def get_password() -> str:
    value = os.getenv("KITE_PASSWORD") or os.getenv("PASSWORD")
    if not value:
        raise RuntimeError("Set KITE_PASSWORD or PASSWORD for TOTP login fallback.")
    return value.strip()


def get_totp_key() -> str:
    value = os.getenv("KITE_TOTP_KEY") or os.getenv("TOTP_KEY")
    if not value:
        raise RuntimeError("Set KITE_TOTP_KEY or TOTP_KEY for TOTP login fallback.")
    return value.strip()


def token_cache_candidates(config_dir: Path | None = None) -> list[Path]:
    candidates = []
    if config_dir is not None:
        candidates.append(config_dir / "access_token_cache.txt")
    candidates.extend(
        [
            Path(__file__).resolve().parent / "access_token_cache.txt",
            repo_root() / "access_token_cache.txt",
        ]
    )
    return candidates


def load_cached_access_token(config_dir: Path | None = None) -> str | None:
    env_token = os.getenv("KITE_ACCESS_TOKEN") or os.getenv("ACCESS_TOKEN")
    if env_token:
        return env_token.strip()

    for path in token_cache_candidates(config_dir):
        if path.exists():
            token = path.read_text(encoding="utf-8").strip()
            if token:
                return token
    return None


def save_access_token(token: str, config_dir: Path | None = None) -> Path:
    candidates = token_cache_candidates(config_dir)
    path = candidates[0] if candidates else Path(__file__).resolve().parent / "access_token_cache.txt"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(token.strip(), encoding="utf-8")
    return path


def kite_call_with_retry(func, *args, **kwargs):
    last_error: Exception | None = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            return func(*args, **kwargs)
        except Exception as exc:
            last_error = exc
            if attempt >= MAX_RETRIES:
                break
            sleep_time = min(2 ** (attempt - 1), MAX_RETRY_DELAY_SECONDS)
            print(f"[kite] {func.__name__} attempt {attempt} failed; retrying in {sleep_time}s: {exc}")
            time.sleep(sleep_time)
    raise RuntimeError(f"Failed Kite call {func.__name__} after {MAX_RETRIES} attempts: {last_error}")


def extract_request_token_from_input(raw_value: str) -> str:
    value = (raw_value or "").strip()
    if not value:
        raise RuntimeError("Empty manual login input; expected request_token or redirected URL.")
    if "request_token=" in value:
        parsed = urlparse(value)
        qs = parse_qs(parsed.query)
        request_tokens = qs.get("request_token", [])
        if request_tokens and request_tokens[0].strip():
            return request_tokens[0].strip()
        raise RuntimeError("Could not extract request_token from redirected URL.")
    return value


def prompt_manual_request_token(login_url: str) -> str:
    if os.getenv("ZERODHA_COLLECTOR_NONINTERACTIVE", "").strip().lower() in {"1", "true", "yes"}:
        raise RuntimeError("Manual Zerodha request_token is required, but noninteractive mode is enabled.")
    print("\n[Manual Login Required] Open this URL, complete login, and paste redirected URL/request_token:")
    print(login_url)
    return extract_request_token_from_input(input("request_token or redirected URL: ").strip())


def generate_access_token(kite) -> str:
    try:
        import pyotp
    except ImportError as exc:
        raise RuntimeError("Install pyotp for TOTP login fallback.") from exc

    api_key = get_api_key()
    login_url = f"https://kite.trade/connect/login?api_key={api_key}"
    session = requests.Session()
    login_resp = session.post(
        "https://kite.zerodha.com/api/login",
        data={"user_id": get_username(), "password": get_password()},
        timeout=30,
    )
    try:
        login_payload = login_resp.json()
    except Exception as exc:
        raise RuntimeError(f"Login endpoint returned non-JSON response. status={login_resp.status_code}") from exc

    login_data = login_payload.get("data") if isinstance(login_payload, dict) else None
    request_id = login_data.get("request_id") if isinstance(login_data, dict) else None
    if not request_id:
        message_text = str(login_payload.get("message", "")).lower() if isinstance(login_payload, dict) else ""
        payload_data = login_payload.get("data", {}) if isinstance(login_payload, dict) else {}
        captcha_required = isinstance(payload_data, dict) and bool(payload_data.get("captcha"))
        if captcha_required or "captcha" in message_text:
            request_token = prompt_manual_request_token(login_url)
            data = kite_call_with_retry(kite.generate_session, request_token, api_secret=get_api_secret())
            return data["access_token"]
        raise RuntimeError(f"Login failed before request_id. status={login_resp.status_code}, payload={login_payload}")

    twofa_resp = session.post(
        "https://kite.zerodha.com/api/twofa",
        data={
            "user_id": get_username(),
            "request_id": request_id,
            "twofa_value": pyotp.TOTP(get_totp_key()).now(),
        },
        timeout=30,
    )
    if twofa_resp.status_code >= 400:
        raise RuntimeError(f"Two-factor step failed. status={twofa_resp.status_code}, payload={twofa_resp.text[:300]}")

    next_url = login_url
    for _ in range(10):
        response = session.get(next_url, allow_redirects=False, timeout=30)
        location = response.headers.get("Location", "")
        parsed = urlparse(location)
        qs = parse_qs(parsed.query)
        if "request_token" in qs:
            request_token = qs["request_token"][0]
            data = kite_call_with_retry(kite.generate_session, request_token, api_secret=get_api_secret())
            return data["access_token"]
        if not location:
            raise RuntimeError("No Location header while following Zerodha login redirect.")
        next_url = location
    raise RuntimeError("No request_token found after following Zerodha login redirects.")


def get_kite_client(config_dir: Path | None = None, allow_login: bool = True):
    load_default_env_files(config_dir)
    try:
        from kiteconnect import KiteConnect
    except ImportError as exc:
        raise RuntimeError("Install kiteconnect: python -m pip install kiteconnect") from exc

    kite = KiteConnect(api_key=get_api_key())
    cached_token = load_cached_access_token(config_dir=config_dir)
    if cached_token:
        kite.set_access_token(cached_token)
        try:
            profile = kite_call_with_retry(kite.profile)
            print(f"[kite] cached token valid for {profile.get('user_name', 'user')} ({profile.get('user_id', 'id')})")
            return kite
        except Exception as exc:
            print(f"[kite] cached token invalid or expired: {exc}")

    if not allow_login:
        raise RuntimeError("No valid cached access token and allow_login=False.")

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            token = generate_access_token(kite)
            kite.set_access_token(token)
            profile = kite_call_with_retry(kite.profile)
            save_path = save_access_token(token, config_dir=config_dir)
            print(f"[kite] logged in as {profile.get('user_name', 'user')} ({profile.get('user_id', 'id')}); token cached at {save_path}")
            return kite
        except Exception as exc:
            if attempt >= MAX_RETRIES:
                raise
            print(f"[kite] login attempt {attempt} failed; retrying in {RETRY_DELAY_SECONDS}s: {exc}")
            time.sleep(RETRY_DELAY_SECONDS)
    return kite


def get_valid_access_token(config_dir: Path | None = None) -> str:
    kite = get_kite_client(config_dir=config_dir)
    token = getattr(kite, "access_token", None)
    if not token:
        token = load_cached_access_token(config_dir)
    if not token:
        raise RuntimeError("Could not determine a valid Kite access token.")
    return str(token)


def get_ticker(config_dir: Path | None = None):
    load_default_env_files(config_dir)
    try:
        from kiteconnect import KiteTicker
    except ImportError as exc:
        raise RuntimeError("Install kiteconnect: python -m pip install kiteconnect") from exc

    return KiteTicker(get_api_key(), get_valid_access_token(config_dir=config_dir))
