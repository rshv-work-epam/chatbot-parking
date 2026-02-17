"""Budget-triggered kill switch (best-effort).

Intended to be called from an Azure Cost Management Budget via an Action Group webhook receiver.
"""

from __future__ import annotations

import json
import os
from typing import Any

import azure.functions as func
from azure.identity import DefaultAzureCredential
import requests

ARM_SCOPE = "https://management.azure.com/.default"


def _env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise ValueError(f"Missing required environment variable: {name}")
    return value


def _arm_post(url: str, *, token: str) -> dict[str, Any]:
    # ARM stop/start operations are async; 202/204 is normal.
    resp = requests.post(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        timeout=30,
    )
    ok = 200 <= resp.status_code < 300
    payload: dict[str, Any] = {
        "ok": ok,
        "status_code": resp.status_code,
    }
    if resp.text:
        try:
            payload["body"] = resp.json()
        except Exception:
            payload["body"] = resp.text[:2000]
    return payload


def main(_req: func.HttpRequest) -> func.HttpResponse:
    try:
        subscription_id = _env("AUTO_STOP_SUBSCRIPTION_ID")
        resource_group = _env("AUTO_STOP_RESOURCE_GROUP")
        container_apps_raw = os.environ.get("AUTO_STOP_CONTAINER_APP_NAMES", "").strip()
        function_app_name = os.environ.get("AUTO_STOP_FUNCTION_APP_NAME", "").strip()
        stop_self = os.environ.get("AUTO_STOP_STOP_FUNCTION_APP", "false").strip().lower() in {"1", "true", "yes"}

        container_apps = [x.strip() for x in container_apps_raw.split(",") if x.strip()]
        if not container_apps and not (stop_self and function_app_name):
            return func.HttpResponse(
                "No targets configured. Set AUTO_STOP_CONTAINER_APP_NAMES and/or AUTO_STOP_STOP_FUNCTION_APP.",
                status_code=400,
            )

        ca_api_version = os.environ.get("AUTO_STOP_CONTAINERAPPS_API_VERSION", "2024-03-01").strip()
        web_api_version = os.environ.get("AUTO_STOP_WEB_API_VERSION", "2024-04-01").strip()

        cred = DefaultAzureCredential(exclude_interactive_browser_credential=True)
        token = cred.get_token(ARM_SCOPE).token

        results: dict[str, Any] = {
            "subscription_id": subscription_id,
            "resource_group": resource_group,
            "stopped": {
                "container_apps": {},
                "function_app": None,
            },
        }

        for name in container_apps:
            url = (
                "https://management.azure.com"
                f"/subscriptions/{subscription_id}"
                f"/resourceGroups/{resource_group}"
                f"/providers/Microsoft.App/containerApps/{name}"
                f"/stop?api-version={ca_api_version}"
            )
            results["stopped"]["container_apps"][name] = _arm_post(url, token=token)

        if stop_self:
            if not function_app_name:
                return func.HttpResponse(
                    "AUTO_STOP_FUNCTION_APP_NAME must be set when AUTO_STOP_STOP_FUNCTION_APP=true",
                    status_code=400,
                )
            url = (
                "https://management.azure.com"
                f"/subscriptions/{subscription_id}"
                f"/resourceGroups/{resource_group}"
                f"/providers/Microsoft.Web/sites/{function_app_name}"
                f"/stop?api-version={web_api_version}"
            )
            results["stopped"]["function_app"] = _arm_post(url, token=token)

        return func.HttpResponse(
            body=json.dumps(results, ensure_ascii=True, sort_keys=True),
            status_code=200,
            mimetype="application/json",
        )
    except Exception as exc:
        return func.HttpResponse(f"budget_stop failed: {exc}", status_code=500)

