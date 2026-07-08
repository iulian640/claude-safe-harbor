#!/usr/bin/env python3
"""safe-harbor usage estimator.

Estimates how much of your weekly Claude subscription quota you have burned,
from inside a session, by summing the token usage recorded in your local
Claude Code transcripts and comparing it against a figure you calibrate from
the real `/usage` reading.

It is an ESTIMATE, not a fuel gauge. It only sees Claude Code usage on this
machine (not claude.ai web, the API, or other devices), and the exact
weighting Anthropic applies toward the weekly limit is not public, so the
scale is fixed by calibration. Treat it as a conservative early warning:
trigger the safe-harbor wrap-up around the margin you set, not at the exact
number.

Commands:
  scan                  Sum weighted tokens over the rolling window, by model.
  calibrate <percent>   Record "right now /usage says <percent>%" and derive
                        the tokens->percent factor.
  estimate              Print the estimated weekly-usage percent (needs a
                        calibration first). Exit code 2 if over the trigger.
  (no arg)              estimate if calibrated, else scan.

Config lives in ~/.claude/safe-harbor.json.
"""
import sys
import json
import glob
import os
from datetime import datetime, timezone, timedelta

HOME = os.path.expanduser("~")
PROJECTS = os.path.join(HOME, ".claude", "projects")
CONFIG = os.path.join(HOME, ".claude", "safe-harbor.json")

DEFAULTS = {
    "plan": "unknown",
    "window_days": 7,
    "trigger_percent": 85.0,
    # Per-token component weights. Output is the expensive part; cache reads are
    # cheap. These are proxies; calibration absorbs the overall scale, so only
    # the relative shape matters here.
    "component_weights": {
        "output": 5.0,
        "input": 1.0,
        "cache_creation": 1.25,
        "cache_read": 0.1,
    },
    # Per-model weights toward the quota (heavier models burn faster). Matched
    # by substring against the model id. Rough price-shaped proxies.
    "model_weights": {
        "opus": 5.0,
        "fable": 5.0,
        "mythos": 5.0,
        "sonnet": 1.0,
        "haiku": 0.25,
        "default": 1.0,
    },
    "calibrations": [],  # list of {"at": iso, "reported_pct": float, "weighted": float}
}


def load_config():
    cfg = dict(DEFAULTS)
    if os.path.exists(CONFIG):
        try:
            saved = json.loads(open(CONFIG, encoding="utf-8").read())
            cfg.update(saved)
        except Exception:
            pass
    return cfg


def save_config(cfg):
    open(CONFIG, "w", encoding="utf-8").write(json.dumps(cfg, indent=2, ensure_ascii=False))


def model_weight(cfg, model):
    m = (model or "").lower()
    for key, w in cfg["model_weights"].items():
        if key != "default" and key in m:
            return w
    return cfg["model_weights"]["default"]


def parse_ts(s):
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return None


def scan(cfg):
    """Sum weighted tokens over the rolling window, grouped by model family."""
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=cfg["window_days"])
    cw = cfg["component_weights"]
    by_model = {}       # model family -> weighted tokens
    raw_by_model = {}   # model family -> raw total tokens (unweighted)
    files = glob.glob(os.path.join(PROJECTS, "**", "*.jsonl"), recursive=True)
    for f in files:
        try:
            fh = open(f, encoding="utf-8")
        except Exception:
            continue
        for line in fh:
            if '"usage"' not in line:
                continue
            try:
                e = json.loads(line)
            except Exception:
                continue
            msg = e.get("message")
            if not isinstance(msg, dict):
                continue
            u = msg.get("usage")
            if not isinstance(u, dict):
                continue
            ts = parse_ts(e.get("timestamp"))
            if ts is None or ts < cutoff:
                continue
            model = msg.get("model") or "unknown"
            fam = next((k for k in cfg["model_weights"] if k != "default" and k in model.lower()), model)
            inp = u.get("input_tokens", 0) or 0
            out = u.get("output_tokens", 0) or 0
            cc = u.get("cache_creation_input_tokens", 0) or 0
            cr = u.get("cache_read_input_tokens", 0) or 0
            weighted = model_weight(cfg, model) * (
                out * cw["output"] + inp * cw["input"] + cc * cw["cache_creation"] + cr * cw["cache_read"]
            )
            by_model[fam] = by_model.get(fam, 0.0) + weighted
            raw_by_model[fam] = raw_by_model.get(fam, 0) + inp + out + cc + cr
    total = sum(by_model.values())
    return total, by_model, raw_by_model, len(files)


def cmd_scan(cfg):
    total, by_model, raw, nfiles = scan(cfg)
    print(f"safe-harbor scan: rolling {cfg['window_days']}d, {nfiles} transcript files")
    for fam in sorted(by_model, key=lambda k: -by_model[k]):
        print(f"  {fam:12} weighted={by_model[fam]:>15,.0f}   raw={raw.get(fam,0):>15,}")
    print(f"  {'TOTAL':12} weighted={total:>15,.0f}")
    return total


def cmd_calibrate(cfg, percent):
    total, _, _, _ = scan(cfg)
    if total <= 0:
        print("No usage found in the window; cannot calibrate.")
        return 1
    cfg["calibrations"].append({
        "at": datetime.now(timezone.utc).isoformat(),
        "reported_pct": float(percent),
        "weighted": total,
    })
    save_config(cfg)
    factor = float(percent) / total
    print(f"Calibrated: {percent}% == {total:,.0f} weighted tokens (factor {factor:.3e} %/token).")
    print("From now on `estimate` uses this. Re-calibrate when your usage mix shifts.")
    return 0


def cmd_estimate(cfg):
    if not cfg["calibrations"]:
        print("Not calibrated yet. Run: usage.py calibrate <the % that /usage shows right now>")
        return 1
    cal = cfg["calibrations"][-1]
    total, by_model, _, _ = scan(cfg)
    factor = cal["reported_pct"] / cal["weighted"] if cal["weighted"] else 0
    est = total * factor
    trig = cfg["trigger_percent"]
    mix = ", ".join(f"{k} {100*v/total:.0f}%" for k, v in sorted(by_model.items(), key=lambda x: -x[1])) if total else "n/a"
    print(f"safe-harbor estimate: ~{est:.0f}% of weekly quota used (trigger at {trig}%).")
    print(f"  calibrated {cal['at'][:16]} at {cal['reported_pct']}%; window {cfg['window_days']}d; mix: {mix}")
    if est >= trig:
        print(f"  >>> OVER TRIGGER ({est:.0f}% >= {trig}%): run safe-harbor and wrap up.")
        return 2
    print(f"  headroom: ~{trig - est:.0f} points before the trigger.")
    return 0


def main():
    cfg = load_config()
    args = sys.argv[1:]
    if not args:
        return cmd_estimate(cfg) if cfg["calibrations"] else (cmd_scan(cfg) and 0)
    cmd = args[0]
    if cmd == "scan":
        cmd_scan(cfg)
        return 0
    if cmd == "calibrate":
        if len(args) < 2:
            print("Usage: usage.py calibrate <percent>")
            return 1
        return cmd_calibrate(cfg, args[1])
    if cmd == "estimate":
        return cmd_estimate(cfg)
    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main())
