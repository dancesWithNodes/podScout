![GitHub Repo Banner](https://ghrb.waren.build/banner?header=%21%5Bpython%5D+podScout&subheader=Lean+RunPod+GPU+watcher.+Network-volume+aware.&bg=431586-9231A8&color=FFFFFF&headerfont=Permanent+Marker&subheaderfont=Kinewave&watermarkpos=bottom-right)
<!-- Created with GitHub Repo Banner by Waren Gonzaga: https://ghrb.waren.build -->

# podScout

Lean RunPod GPU watcher. Network-volume aware.

No UI. No dashboards. No watching the marketplace like a dying heart monitor.

Just signal.

## 🚀 Quick Start

### Requirements

- Python 3.9+
- RunPod API key

### Optional

- Pushover App Token & User Key for notifications

### Install

```bash
pip install requests
```

### Set secrets

```bash
export RUNPOD_API_KEY=your_key
export PUSHOVER_APP_TOKEN=your_token
export PUSHOVER_USER_KEY=your_user
```

### Run

```bash
python podScout.py
```

## ⚙️ Config

Edit values at the top of `podScout.py`.

Environment variables win. Fallbacks exist. Do not commit secrets.

### Key fields

- `WATCH_GPU_TYPE_IDS`
- `DATACENTER_ID`
- `NETWORK_VOLUME_ID`
- `MARKET_MODE`
- `ENABLE_PUSHOVER`

Prefer internal `gpuTypeId` values. Display names may work until they do not.

## 📐 Routing Logic

Deterministic:

1. `DATACENTER_ID` -> used.
2. Else `NETWORK_VOLUME_ID` -> infer datacenter.
3. Else -> global.
4. If both disagree -> exit.

No guessing. No silent overrides.

Using a network volume? Your pod must spawn in the same datacenter as the storage.
If that datacenter has no GPUs available, you are stuck watching nothing happen.

This script tells you that quickly.

## 🧪 CLI Flags (or lack thereof)

### `--once`

Exit codes:

- `0` -> available
- `1` -> not available
- `2` -> error
- Anything else -> error

No flag zoo.

## 🔔 Notifications

Optional. Disabled by default.

- State-change mode
- Periodic mode
- Cooldowns enforced

No notification storms.

## 📜 Philosophy

Fail fast. No hidden config. No external JSON. No feature creep.

It polls. It checks. It notifies.

If GPUs exist, you will know.
If they do not, at least you will not waste an hour clicking refresh.

That is it.

## 🤖 AI Assistance

Portions of this project were generated or refined with the assistance of GPT-5.x (Codex).  
Core logic and design decisions are mine. Boilerplate and repetitive scaffolding were delegated.

Human-reviewed. No blind merges.
