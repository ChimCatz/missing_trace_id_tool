from __future__ import annotations

import io
import json
import os
import sys
import zipfile
from dataclasses import dataclass
from pathlib import Path
from time import sleep
from time import time
from typing import Any

import pandas as pd
import requests
from requests import Response
from requests.exceptions import RequestException

DEFAULT_ACCOUNTS_URL = "https://accounts.zoho.com"
DEFAULT_API_DOMAIN = "https://www.zohoapis.com"
CRM_API_VERSION = "v8"
BULK_READ_VERSION = "v8"
POLL_INTERVAL_SECONDS = 1
DEFAULT_LEADS_MODULE = "Leads"
DEFAULT_COMPANY_REGISTRY_MODULE = "Company_Registry"


def get_runtime_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def get_cache_root() -> Path:
    if sys.platform.startswith("win"):
        local_appdata = Path(
            os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local"))
        )
        return local_appdata / "Missing Trace Company ID Tool"
    return Path.home() / ".missing-trace-company-id-tool"


DEFAULT_ENV_PATH = get_runtime_root() / ".env"
DEFAULT_CACHE_PATH = get_cache_root() / ".zoho_cache.json"


@dataclass(frozen=True)
class ZohoConfig:
    client_id: str
    client_secret: str
    refresh_token: str
    accounts_url: str = DEFAULT_ACCOUNTS_URL
    api_domain: str = DEFAULT_API_DOMAIN
    leads_module: str = DEFAULT_LEADS_MODULE
    company_registry_module: str = DEFAULT_COMPANY_REGISTRY_MODULE

    @property
    def token_url(self) -> str:
        return f"{self.accounts_url.rstrip('/')}/oauth/v2/token"


def load_env_file(env_path: str | Path = DEFAULT_ENV_PATH) -> dict[str, str]:
    path = Path(env_path)
    if not path.exists():
        raise FileNotFoundError(
            f"{path} not found. Add a Zoho .env file beside the app executable."
        )

    env: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        env[key.strip()] = value.strip()
    return env


def load_config(env_path: str | Path = DEFAULT_ENV_PATH) -> ZohoConfig:
    env = load_env_file(env_path)
    required_keys = [
        "ZOHO_CLIENT_ID",
        "ZOHO_CLIENT_SECRET",
        "ZOHO_REFRESH_TOKEN",
    ]
    missing_keys = [key for key in required_keys if not env.get(key)]
    if missing_keys:
        missing = ", ".join(missing_keys)
        raise ValueError(f"Missing required .env setting(s): {missing}")

    return ZohoConfig(
        client_id=env["ZOHO_CLIENT_ID"],
        client_secret=env["ZOHO_CLIENT_SECRET"],
        refresh_token=env["ZOHO_REFRESH_TOKEN"],
        accounts_url=env.get("ZOHO_ACCOUNTS_URL", DEFAULT_ACCOUNTS_URL),
        api_domain=env.get("ZOHO_API_DOMAIN", DEFAULT_API_DOMAIN),
        leads_module=env.get("ZOHO_LEADS_MODULE", DEFAULT_LEADS_MODULE),
        company_registry_module=env.get(
            "ZOHO_COMPANY_REGISTRY_MODULE",
            DEFAULT_COMPANY_REGISTRY_MODULE,
        ),
    )


def load_cache_file(cache_path: str | Path = DEFAULT_CACHE_PATH) -> dict[str, Any]:
    path = Path(cache_path)
    if not path.exists():
        return {"tokens": {}}

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"tokens": {}}

    if not isinstance(data, dict):
        return {"tokens": {}}

    data.setdefault("tokens", {})
    return data


def write_cache_file(
    cache_data: dict[str, Any],
    cache_path: str | Path = DEFAULT_CACHE_PATH,
) -> None:
    path = Path(cache_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(cache_data, indent=2, ensure_ascii=True),
        encoding="utf-8",
    )


def format_scope_guidance(payload: dict[str, Any], action: str) -> str | None:
    if payload.get("code") != "OAUTH_SCOPE_MISMATCH":
        return None

    return (
        f"{action} failed because the OAuth token is missing the required Zoho "
        "CRM scopes. Regenerate the refresh token with at least "
        "`ZohoCRM.modules.ALL`, `ZohoCRM.settings.ALL`, and "
        "`ZohoCRM.bulk.read`."
    )


def raise_for_zoho_error(response: Response, action: str) -> None:
    try:
        response.raise_for_status()
    except RequestException as exc:
        snippet = response.text[:500]
        try:
            payload = response.json()
        except ValueError:
            payload = None
        if isinstance(payload, dict):
            scope_guidance = format_scope_guidance(payload, action)
            if scope_guidance:
                raise RuntimeError(scope_guidance) from exc
        raise RuntimeError(
            f"{action} failed with HTTP {response.status_code}: {snippet}"
        ) from exc


def parse_json_response(response: Response, action: str) -> dict[str, Any]:
    raise_for_zoho_error(response, action)
    try:
        return response.json()
    except ValueError as exc:
        snippet = response.text[:500]
        raise RuntimeError(f"{action} returned non-JSON content: {snippet}") from exc


def format_request_exception(action: str, exc: RequestException) -> RuntimeError:
    return RuntimeError(
        f"{action} could not reach Zoho. Check your internet connection, proxy "
        f"settings, or firewall. Original error: {exc}"
    )


class ZohoClient:
    _token_cache: dict[tuple[str, str, str], dict[str, Any]] = {}

    def __init__(self, config: ZohoConfig) -> None:
        self.config = config
        self.session = requests.Session()
        self._access_token: str | None = None
        self._api_domain: str | None = None
        self._expires_at: float | None = None

    def close(self) -> None:
        self.session.close()

    def __enter__(self) -> "ZohoClient":
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.close()

    @property
    def api_domain(self) -> str:
        if self._api_domain:
            return self._api_domain
        return self.config.api_domain.rstrip("/")

    def get_access_token(self, *, force_refresh: bool = False) -> dict[str, Any]:
        cache_key = (
            self.config.client_id,
            self.config.refresh_token,
            self.config.accounts_url.rstrip("/"),
        )
        cache_key_text = "|".join(cache_key)
        now = time()

        if (
            self._access_token
            and self._expires_at is not None
            and now < self._expires_at
            and not force_refresh
        ):
            return {
                "access_token": self._access_token,
                "api_domain": self.api_domain,
            }

        cached_token = self._token_cache.get(cache_key)
        if (
            cached_token
            and not force_refresh
            and now < float(cached_token["expires_at"])
        ):
            self._access_token = str(cached_token["access_token"])
            self._api_domain = str(cached_token["api_domain"]).rstrip("/")
            self._expires_at = float(cached_token["expires_at"])
            return {
                "access_token": self._access_token,
                "api_domain": self._api_domain,
                "expires_in": max(0, int(self._expires_at - now)),
            }

        disk_cache = load_cache_file()
        disk_cached_token = disk_cache["tokens"].get(cache_key_text)
        if (
            isinstance(disk_cached_token, dict)
            and not force_refresh
            and now < float(disk_cached_token.get("expires_at", 0))
        ):
            self._access_token = str(disk_cached_token["access_token"])
            self._api_domain = str(disk_cached_token["api_domain"]).rstrip("/")
            self._expires_at = float(disk_cached_token["expires_at"])
            self._token_cache[cache_key] = {
                "access_token": self._access_token,
                "api_domain": self._api_domain,
                "expires_at": self._expires_at,
            }
            return {
                "access_token": self._access_token,
                "api_domain": self._api_domain,
                "expires_in": max(0, int(self._expires_at - now)),
            }

        payload = {
            "refresh_token": self.config.refresh_token,
            "client_id": self.config.client_id,
            "client_secret": self.config.client_secret,
            "grant_type": "refresh_token",
        }
        try:
            response = self.session.post(
                self.config.token_url,
                data=payload,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=30,
            )
        except RequestException as exc:
            raise format_request_exception("Access token request", exc) from exc
        token_data = parse_json_response(response, "Access token request")

        if token_data.get("error") == "invalid_code":
            raise RuntimeError(
                "Zoho returned `invalid_code`. The current refresh token is "
                "invalid, revoked, or tied to a different client."
            )

        access_token = token_data.get("access_token")
        if not access_token:
            raise RuntimeError(f"Zoho did not return an access token: {token_data}")

        self._access_token = access_token
        self._api_domain = token_data.get("api_domain", self.config.api_domain).rstrip(
            "/"
        )
        expires_in = int(token_data.get("expires_in", 3600) or 3600)
        self._expires_at = now + max(60, expires_in - 120)
        self._token_cache[cache_key] = {
            "access_token": self._access_token,
            "api_domain": self._api_domain,
            "expires_at": self._expires_at,
        }
        disk_cache["tokens"][cache_key_text] = {
            "access_token": self._access_token,
            "api_domain": self._api_domain,
            "expires_at": self._expires_at,
        }
        write_cache_file(disk_cache)
        return {
            "access_token": self._access_token,
            "api_domain": self._api_domain,
            "expires_in": expires_in,
        }

    def get_headers(self) -> dict[str, str]:
        token_info = self.get_access_token()
        return {"Authorization": f"Zoho-oauthtoken {token_info['access_token']}"}

    def _get_json(
        self,
        url: str,
        action: str,
        *,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        try:
            response = self.session.get(
                url,
                params=params,
                headers=self.get_headers(),
                timeout=30,
            )
        except RequestException as exc:
            raise format_request_exception(action, exc) from exc
        payload = parse_json_response(response, action)
        scope_guidance = format_scope_guidance(payload, action)
        if scope_guidance:
            raise RuntimeError(scope_guidance)
        return payload

    def create_bulk_read_job(self, module_api_name: str, fields: list[str]) -> str:
        url = f"{self.api_domain}/crm/bulk/{BULK_READ_VERSION}/read"
        payload = {
            "query": {
                "module": {"api_name": module_api_name},
                "fields": fields,
                "page": 1,
            }
        }
        try:
            response = self.session.post(
                url,
                headers=self.get_headers(),
                json=payload,
                timeout=30,
            )
        except RequestException as exc:
            raise format_request_exception(
                f"Bulk Read job creation for module {module_api_name}",
                exc,
            ) from exc
        job_data = parse_json_response(
            response,
            f"Bulk Read job creation for module {module_api_name}",
        )
        scope_guidance = format_scope_guidance(
            job_data,
            f"Bulk Read job creation for module {module_api_name}",
        )
        if scope_guidance:
            raise RuntimeError(scope_guidance)

        try:
            return job_data["data"][0]["details"]["id"]
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError(
                f"Unexpected Bulk Read creation response: {job_data}"
            ) from exc

    def wait_for_bulk_read_completion(
        self,
        job_id: str,
        *,
        status_callback: Any = None,
    ) -> None:
        url = f"{self.api_domain}/crm/bulk/{BULK_READ_VERSION}/read/{job_id}"
        while True:
            try:
                response = self.session.get(
                    url,
                    headers=self.get_headers(),
                    timeout=30,
                )
            except RequestException as exc:
                raise format_request_exception("Bulk Read job status check", exc) from exc
            payload = parse_json_response(response, "Bulk Read job status check")
            scope_guidance = format_scope_guidance(
                payload,
                "Bulk Read job status check",
            )
            if scope_guidance:
                raise RuntimeError(scope_guidance)

            try:
                state = payload["data"][0]["state"]
            except (KeyError, IndexError, TypeError) as exc:
                raise RuntimeError(
                    f"Unexpected Bulk Read status response: {payload}"
                ) from exc

            if status_callback:
                status_callback(f"Bulk Read job status: {state}")
            if state == "COMPLETED":
                return
            if state in {"FAILED", "FAILURE"}:
                raise RuntimeError(f"Bulk Read job failed: {payload}")

            sleep(POLL_INTERVAL_SECONDS)

    def download_bulk_read_result(
        self,
        job_id: str,
        *,
        status_callback: Any = None,
    ) -> pd.DataFrame:
        url = f"{self.api_domain}/crm/bulk/{BULK_READ_VERSION}/read/{job_id}/result"
        if status_callback:
            status_callback("Downloading Bulk Read result...")
        try:
            response = self.session.get(url, headers=self.get_headers(), timeout=60)
        except RequestException as exc:
            raise format_request_exception("Bulk Read result download", exc) from exc
        raise_for_zoho_error(response, "Bulk Read result download")

        try:
            with zipfile.ZipFile(io.BytesIO(response.content)) as zipped_file:
                csv_names = [
                    name for name in zipped_file.namelist() if name.lower().endswith(".csv")
                ]
                if not csv_names:
                    raise RuntimeError(
                        "Downloaded ZIP did not contain a CSV file: "
                        f"{zipped_file.namelist()}"
                    )

                with zipped_file.open(csv_names[0]) as csv_file:
                    return pd.read_csv(csv_file, dtype=str, keep_default_na=False)
        except zipfile.BadZipFile as exc:
            snippet = response.text[:500]
            raise RuntimeError(
                f"Downloaded result was not a valid ZIP file: {snippet}"
            ) from exc

    def fetch_module_dataframe(
        self,
        module_api_name: str,
        fields: list[str],
        *,
        status_callback: Any = None,
    ) -> pd.DataFrame:
        if not fields:
            raise RuntimeError(f"No fields were provided for module {module_api_name}.")

        if status_callback:
            status_callback(
                f"Creating Bulk Read job for {module_api_name} "
                f"with {len(fields)} fields..."
            )
        job_id = self.create_bulk_read_job(module_api_name, fields)
        if status_callback:
            status_callback(f"Bulk Read job created: {job_id}")
        self.wait_for_bulk_read_completion(job_id, status_callback=status_callback)
        return self.download_bulk_read_result(job_id, status_callback=status_callback)
