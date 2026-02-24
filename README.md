![GitHub Repo Banner](https://ghrb.waren.build/banner?header=%21%5Bpython%5D+podScout&subheader=Lean+RunPod+GPU+watcher.+Network-volume+aware.&bg=431586-9231A8&color=FFFFFF&headerfont=Permanent+Marker&subheaderfont=Kinewave&watermarkpos=bottom-right)
<!-- Created with GitHub Repo Banner by Waren Gonzaga: https://ghrb.waren.build -->

# podScout

Lean RunPod GPU watcher. Network-volume aware.  
No UI. No dashboards. Just signal.

Author: dancesWithNodes  
License: MIT  

---

## 🎯 What This Does

Polls RunPod’s API.  
Checks availability for specific GPU types.  
Optionally restricts to a datacenter.  
Optionally infers that datacenter from a network volume.  
Optionally sends Pushover notifications.  

That’s it.

If a GPU becomes available, you’ll know.  
If it doesn’t, you’ll wait. Like the rest of us.

---

## 🧠 Design Principles

- Explicit wins.
- Environment variables override fallbacks.
- Fail fast.
- No magic.
- No external config files.
- One flag. `--once`. That’s the list.

If something is misconfigured, it errors. Immediately.  
If an API field changes, it retries. Then errors.

Garbage in, garbage out.

---

## ⚙ Configuration

Edit variables at the top of `podScout.py`.

Secrets should be provided via environment variables:

```
export RUNPOD_API_KEY=your_key
export PUSHOVER_APP_TOKEN=your_token
export PUSHOVER_USER_KEY=your_user
```

Fallback constants exist for local testing.  
Env vars win.

### Region Routing Logic

Precedence is explicit:

1. `DATACENTER_ID` set → used directly.
2. Else if `NETWORK_VOLUME_ID` set → datacenter inferred from volume.
3. Else → global pool.

If both are set and disagree → hard failure.  
No guessing.

---

## 🌐 Market Mode

`MARKET_MODE` supports:

- `secure`
- `community`
- `both`
- `""` (auto)

Auto mode:
- If `NETWORK_VOLUME_ID` exists → defaults to `secure`
- Else → defaults to `both`

Deterministic. No surprises.

---

## 🖥 GPU Targets

Use `WATCH_GPU_TYPE_IDS`.

Prefer internal `gpuTypeId` values.  
Display names may work. Until they don’t.

Example:

```python
WATCH_GPU_TYPE_IDS = [
    "NVIDIA GeForce RTX 5090",
]
```

If this list is empty → error.  
Because of course.

---

## 📊 Availability Classification

Availability is derived from:

- `maxUnreservedGpuCount`
- `availableGpuCounts`

Logic:

- 0 → 🔴 Unavailable
- 1 → 🟠 Low
- 2 → 🟡 Medium
- ≥3 → 🟢 High

If the API returns nothing → treated as unavailable.  
No dice.

---

## 🔔 Notifications

Optional. Disabled by default.

Two modes:

### State Change Mode (default)

Notify only when availability changes from false → true.  
Cooldown controlled by:

```
STATE_CHANGE_NOTIFY_COOLDOWN_SECONDS
```

### Periodic Mode

Notify repeatedly while available.  
Cooldown controlled by:

```
PUSHOVER_COOLDOWN_SECONDS
```

If cooldown active → suppressed. Calmly.

---

## 🧪 CLI Flags

Supported flags:

```
--once
```

That’s it.

Behavior:

- Runs a single check.
- Exit code `0` if any GPU available.
- Exit code `1` if none available.
- Exit code `2` on error.

Any other flag → immediate failure.

No argparse circus. No shorthand flags. No config files.

---

## 📦 Installation

Requires Python 3.9+

Dependency:

```
pip install requests
```

That’s the only one.

---

## ▶ Run

Continuous mode:

```
python podScout.py
```

Single check:

```
python podScout.py --once
```

---

## 💥 Failure Modes

Common examples:

- Missing `RUNPOD_API_KEY` → error.
- Invalid `DATACENTER_ID` → validation fails.
- Volume cannot resolve datacenter → error.
- Unknown CLI argument → error.

Messages are blunt.  
You’ll know what broke.

---

## 🤖 AI Assistance

Portions of this project were generated or refined with the assistance of GPT-5.x (Codex).  
Core logic and design decisions are mine. Boilerplate and repetitive scaffolding were delegated.

Human-reviewed. No blind merges.

---

## 🧾 License

MIT

Do what you want.  
If it works, great.  
If it doesn’t, you have the source.
