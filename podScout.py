#!/usr/bin/env python3
r"""
               _ ___              _   
 _ __  ___  __| / __| __ ___ _  _| |_ 
| '_ \/ _ \/ _` \__ \/ _/ _ \ || |  _|
| .__/\___/\__,_|___/\__\___/\_,_|\__|
|_|                               v1.0

Author: dancesWithNodes
Released: 2026-02-24
License: MIT

Description:
Lean RunPod GPU watcher. Network-volume aware.
Coded by me, pimped by GPT-5.3-Codex.

Instructions:
1) Configure variables at the top of the script (API keys via environment variables recommended).
2) Install dependency: pip install requests
3) Run. May your time in GPU limbo be brief.
"""

from __future__ import annotations

import os
import sys
import time
from datetime import datetime
from typing import Any

import requests

# ===================== Minimal Config =====================
# Env vars win. Fallbacks exist for local testing.
RUNPOD_API_KEY_FALLBACK = ""
PUSHOVER_APP_TOKEN_FALLBACK = ""
PUSHOVER_USER_KEY_FALLBACK = ""

# Region routing:
# - Explicit DATACENTER_ID wins.
# - Else, if NETWORK_VOLUME_ID exists, infer datacenter from the volume.
DATACENTER_ID = ""
NETWORK_VOLUME_ID = ""

# "secure", "community", "both", or "" for auto mode.
MARKET_MODE = ""

# Prefer gpuTypeId values. Display names may work, until they don't.
WATCH_GPU_TYPE_IDS = [
    # "NVIDIA GeForce RTX 4090",
    "NVIDIA GeForce RTX 5090",
    # "NVIDIA RTX PRO 6000 Blackwell Server Edition",
    # "NVIDIA L40S",
    # "NVIDIA H200",
    # "NVIDIA B200",
]

# Backward compatibility for older config blocks.
WATCH_GPUS = WATCH_GPU_TYPE_IDS

GPU_COUNT = 1
REFRESH_SECONDS = 10
PUSHOVER_COOLDOWN_SECONDS = 200
STATE_CHANGE_NOTIFY_COOLDOWN_SECONDS = 30
ENABLE_PUSHOVER = False
NOTIFY_ON_AVAILABILITY_CHANGE_ONLY = True
PRINT_ON_AVAILABILITY_CHANGE_ONLY = False
TIMEOUT_SECONDS = 30
# ======================================================

GRAPHQL_URL = "https://api.runpod.io/graphql"
VOLUME_URL = "https://rest.runpod.io/v1/networkvolumes/{volume_id}"
PUSHOVER_URL = "https://api.pushover.net/1/messages.json"

GPU_QUERY_NEW = """
query($gpuTypeId: String!, $lp: GpuLowestPriceInput!) {
  gpuTypes(input: { id: $gpuTypeId }) {
    displayName
    memoryInGb
    lowestPrice(input: $lp) {
      stockStatus
      maxUnreservedGpuCount
      availableGpuCounts
      uninterruptablePrice
    }
  }
}
"""

GPU_QUERY_LEGACY = """
query($gpuTypeId: String!, $lp: GpuTypeLowestPriceInput!) {
  gpuTypes(input: { id: $gpuTypeId }) {
    displayName
    memoryInGb
    lowestPrice(input: $lp) {
      stockStatus
      maxUnreservedGpuCount
      availableGpuCounts
      uninterruptablePrice
    }
  }
}
"""


def ts() -> str:
    return datetime.now().strftime("%H:%M:%S")


def log(message: str) -> None:
    print(f"{ts()} {message}", flush=True)


def short_gpu_name(name: str) -> str:
    for prefix in ("NVIDIA GeForce ", "NVIDIA "):
        if name.startswith(prefix):
            return name[len(prefix):]
    return name


def require_secrets() -> tuple[str, str | None, str | None]:
    runpod_api_key = (os.getenv("RUNPOD_API_KEY") or RUNPOD_API_KEY_FALLBACK).strip()
    pushover_token = (os.getenv("PUSHOVER_APP_TOKEN") or PUSHOVER_APP_TOKEN_FALLBACK).strip()
    pushover_user = (os.getenv("PUSHOVER_USER_KEY") or PUSHOVER_USER_KEY_FALLBACK).strip()

    if not runpod_api_key:
        raise RuntimeError("RUNPOD_API_KEY is required (env var or fallback config value).")

    if ENABLE_PUSHOVER and (not pushover_token or not pushover_user):
        raise RuntimeError(
            "ENABLE_PUSHOVER is True, but PUSHOVER_APP_TOKEN and PUSHOVER_USER_KEY are missing."
        )

    return runpod_api_key, (pushover_token or None), (pushover_user or None)


def resolve_datacenter_id_from_volume(session: requests.Session, volume_id: str) -> str:
    response = session.get(VOLUME_URL.format(volume_id=volume_id), timeout=TIMEOUT_SECONDS)
    response.raise_for_status()
    payload = response.json()

    if isinstance(payload, dict):
        dc = payload.get("dataCenterId")
        if not dc and isinstance(payload.get("data"), dict):
            dc = payload["data"].get("dataCenterId")
        if dc:
            return str(dc)

    raise RuntimeError("Unable to determine dataCenterId from network volume response.")


def fetch_gpu_row(
    session: requests.Session,
    gpu_type_id: str,
    datacenter_id: str | None,
    secure_cloud: bool,
) -> dict[str, Any]:
    lp_base: dict[str, Any] = {
        "secureCloud": secure_cloud,
        "gpuCount": GPU_COUNT,
        "globalNetwork": not secure_cloud,
    }
    if datacenter_id:
        lp_base["dataCenterId"] = datacenter_id

    attempts = [
        (GPU_QUERY_NEW, "minDisk"),
        (GPU_QUERY_NEW, "minDiskInGb"),
        (GPU_QUERY_LEGACY, "minDisk"),
        (GPU_QUERY_LEGACY, "minDiskInGb"),
    ]
    last_error: Exception | None = None

    for query, disk_field in attempts:
        lp = dict(lp_base)
        lp[disk_field] = 0

        try:
            response = session.post(
                GRAPHQL_URL,
                json={"query": query, "variables": {"gpuTypeId": gpu_type_id, "lp": lp}},
                timeout=TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            payload = response.json()
            if payload.get("errors"):
                raise RuntimeError(str(payload["errors"]))

            rows = (((payload or {}).get("data") or {}).get("gpuTypes") or [])
            if not rows:
                return {"found": False, "requested": gpu_type_id}

            gpu = rows[0] or {}
            lowest = gpu.get("lowestPrice") or {}
            return {
                "found": True,
                "name": gpu.get("displayName") or gpu_type_id,
                "vram": gpu.get("memoryInGb"),
                "stock": lowest.get("stockStatus"),
                "max_unreserved": lowest.get("maxUnreservedGpuCount") or 0,
                "counts": lowest.get("availableGpuCounts") or [],
                "price": lowest.get("uninterruptablePrice"),
            }
        except Exception as err:  # pylint: disable=broad-except
            last_error = err

    raise RuntimeError(f"GPU lookup failed for '{gpu_type_id}': {last_error}")


def validate_datacenter_id(
    session: requests.Session,
    datacenter_id: str,
    gpu_type_id: str,
    markets: list[tuple[str, bool]],
) -> None:
    last_error: Exception | None = None
    for market_label, is_secure in markets:
        try:
            row = fetch_gpu_row(session, gpu_type_id, datacenter_id, secure_cloud=is_secure)
            if row.get("found"):
                return
            last_error = RuntimeError(
                f"lookup returned no gpuTypes row for '{gpu_type_id}' in {market_label} market"
            )
        except Exception as err:  # pylint: disable=broad-except
            last_error = err

    raise RuntimeError(
        f"DATACENTER_ID '{datacenter_id}' failed validation. Invalid value or API rejected it. {last_error}"
    )


def classify_availability(row: dict[str, Any]) -> tuple[str, str, bool]:
    if not row.get("found"):
        return "🔴", "Unavailable", False

    max_unreserved = row.get("max_unreserved")
    counts = row.get("counts")
    counts = counts if isinstance(counts, list) else []
    max_count = 0
    for val in counts:
        if isinstance(val, int) and val > max_count:
            max_count = val

    available_count = 0
    if isinstance(max_unreserved, int) and max_unreserved > 0:
        available_count = max_unreserved
    if max_count > available_count:
        available_count = max_count

    if available_count <= 0:
        return "🔴", "Unavailable", False
    if available_count >= 3:
        return "🟢", "High Availability", True
    if available_count == 2:
        return "🟡", "Medium Availability", True
    return "🟠", "Low Availability", True


def format_price(value: Any) -> str:
    if isinstance(value, (int, float)):
        return f"${value:.2f}/hr"
    return "$?/hr"


def send_pushover(
    session: requests.Session,
    token: str,
    user_key: str,
    title: str,
    message: str,
) -> None:
    response = session.post(
        PUSHOVER_URL,
        data={
            "token": token,
            "user": user_key,
            "title": title,
            "message": message,
        },
        timeout=TIMEOUT_SECONDS,
    )
    response.raise_for_status()


def parse_args(argv: list[str]) -> bool:
    once = False
    for arg in argv:
        if arg == "--once":
            once = True
            continue
        raise RuntimeError(f"Unknown argument: {arg}")
    return once


def main(once: bool = False) -> int:
    runpod_key, pushover_token, pushover_user = require_secrets()

    runpod = requests.Session()
    runpod.headers.update(
        {
            "Authorization": f"Bearer {runpod_key}",
            "Accept": "application/json",
            "User-Agent": "podScout/1.0",
        }
    )
    pushover = requests.Session()
    pushover.headers.update({"User-Agent": "podScout/1.0"})

    last_pushover_sent_at = 0.0
    last_any_available: bool | None = None

    try:
        print("podScout v1.0 - monitor runpod gpu availability...", flush=True)
        if PRINT_ON_AVAILABILITY_CHANGE_ONLY:
            print(
                f"Checking every {REFRESH_SECONDS} seconds, will print on state change.",
                flush=True,
            )
        if ENABLE_PUSHOVER:
            if NOTIFY_ON_AVAILABILITY_CHANGE_ONLY:
                print(
                    "Pushover enabled. Notify mode: state change only "
                    f"({STATE_CHANGE_NOTIFY_COOLDOWN_SECONDS}s cooldown).",
                    flush=True,
                )
            else:
                print(
                    "Pushover enabled. Notify mode: periodic while available "
                    f"({PUSHOVER_COOLDOWN_SECONDS}s cooldown).",
                    flush=True,
                )
        print("", flush=True)

        # No mode configured. Use the least surprising default.
        mode = (MARKET_MODE or ("secure" if NETWORK_VOLUME_ID else "both")).strip().lower()
        if mode not in {"secure", "community", "both"}:
            raise RuntimeError("MARKET_MODE must be one of: secure, community, both")

        markets: list[tuple[str, bool]]
        if mode == "both":
            markets = [("SECURE", True), ("COMMUNITY", False)]
        elif mode == "community":
            markets = [("COMMUNITY", False)]
        else:
            markets = [("SECURE", True)]

        gpu_targets = WATCH_GPU_TYPE_IDS or WATCH_GPUS
        if not gpu_targets:
            raise RuntimeError("No GPU targets configured. Set WATCH_GPU_TYPE_IDS.")

        datacenter_id = DATACENTER_ID.strip()
        volume_id = NETWORK_VOLUME_ID.strip()
        volume_datacenter_id: str | None = None

        if volume_id:
            try:
                volume_datacenter_id = resolve_datacenter_id_from_volume(runpod, volume_id)
            except Exception as err:  # pylint: disable=broad-except
                raise RuntimeError(
                    f"NETWORK_VOLUME_ID '{volume_id}' is invalid or inaccessible. {err}"
                ) from err

        if datacenter_id and volume_datacenter_id and datacenter_id != volume_datacenter_id:
            raise RuntimeError(
                "DATACENTER_ID and NETWORK_VOLUME_ID disagree. "
                f"DATACENTER_ID='{datacenter_id}', volume resolved to '{volume_datacenter_id}'."
            )

        if not datacenter_id and volume_datacenter_id:
            datacenter_id = volume_datacenter_id
            log(f"Using dataCenterId: {datacenter_id}")
            print("", flush=True)

        if datacenter_id:
            validate_datacenter_id(runpod, datacenter_id, gpu_targets[0], markets)

        while True:
            any_available = False
            first_available_message: str | None = None
            cycle_lines: list[str] = []

            if datacenter_id and (DATACENTER_ID or NETWORK_VOLUME_ID):
                cycle_lines.append(f"Checking GPU Pool for {datacenter_id}...")
            else:
                cycle_lines.append("Checking global GPU Pool...")

            for gpu in gpu_targets:
                for market_label, is_secure in markets:
                    row = fetch_gpu_row(runpod, gpu, datacenter_id, secure_cloud=is_secure)
                    emoji, availability, is_available = classify_availability(row)

                    display_name = short_gpu_name(row.get("name") or row.get("requested") or gpu)
                    vram = row.get("vram")
                    vram_label = f"({vram}GB)" if isinstance(vram, int) else ""

                    if is_available:
                        line = (
                            f"[{market_label}] {display_name} {vram_label} | {emoji} {availability} | "
                            f"{format_price(row.get('price'))}"
                        ).replace("  ", " ").strip()
                        any_available = True
                        if first_available_message is None:
                            first_available_message = line
                    else:
                        line = f"[{market_label}] {display_name} {vram_label} | {emoji} {availability}"
                        line = line.replace("  ", " ").strip()

                    cycle_lines.append(line)

            now = time.monotonic()
            state_changed = (last_any_available is None) or (any_available != last_any_available)
            should_print_cycle = (not PRINT_ON_AVAILABILITY_CHANGE_ONLY) or state_changed
            if once:
                should_print_cycle = True

            if should_print_cycle:
                for line in cycle_lines:
                    log(line)

            if ENABLE_PUSHOVER:
                if NOTIFY_ON_AVAILABILITY_CHANGE_ONLY:
                    if state_changed and any_available and pushover_token and pushover_user and first_available_message:
                        if now - last_pushover_sent_at >= STATE_CHANGE_NOTIFY_COOLDOWN_SECONDS:
                            send_pushover(
                                pushover,
                                pushover_token,
                                pushover_user,
                                "RunPod GPU Available",
                                first_available_message,
                            )
                            last_pushover_sent_at = now
                            if should_print_cycle:
                                log(
                                    "Pushover notification sent "
                                    "(availability state changed)"
                                )
                        elif not PRINT_ON_AVAILABILITY_CHANGE_ONLY:
                            log("Pushover state change detected, but cooldown is active")
                    elif not state_changed and not PRINT_ON_AVAILABILITY_CHANGE_ONLY:
                        log("Pushover suppressed (availability state unchanged)")
                elif any_available:
                    if now - last_pushover_sent_at >= PUSHOVER_COOLDOWN_SECONDS:
                        if pushover_token and pushover_user and first_available_message:
                            send_pushover(
                                pushover,
                                pushover_token,
                                pushover_user,
                                "RunPod GPU Available",
                                first_available_message,
                            )
                            last_pushover_sent_at = now
                            log(
                                "Pushover notification sent "
                                f"({PUSHOVER_COOLDOWN_SECONDS} second cooldown triggered)"
                            )
                    else:
                        if not PRINT_ON_AVAILABILITY_CHANGE_ONLY:
                            log("Pushover notifications currently paused")
            else:
                if not PRINT_ON_AVAILABILITY_CHANGE_ONLY:
                    log(f"Waiting {REFRESH_SECONDS} seconds until next check")

            last_any_available = any_available

            if once:
                return 0 if any_available else 1

            if should_print_cycle:
                print("", flush=True)
            time.sleep(REFRESH_SECONDS)
    finally:
        runpod.close()
        pushover.close()


if __name__ == "__main__":
    try:
        raise SystemExit(main(once=parse_args(sys.argv[1:])))
    except KeyboardInterrupt:
        print("\nStopped.", file=sys.stderr)
        raise SystemExit(130)
    except Exception as err:  # pylint: disable=broad-except
        print(f"Error: {err}", file=sys.stderr)
        raise SystemExit(2)
