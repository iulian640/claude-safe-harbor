#!/usr/bin/env python3
"""safe-harbor usage estimator (multi-meter, reset-anchored).

Estimates how close you are to each of your Claude subscription limits, from
inside a session, by summing the token usage recorded in your local Claude
Code transcripts and scaling each meter against a figure you calibrate from
the real `/usage` reading.

Claude enforces SEVERAL limits at once, each resetting at its own time:
  - the current SESSION window (~5 hours) — the one that bites during bursts,
  - the weekly window across all models,
  - a weekly cap for premium models (e.g. Fable) with its own ceiling.
safe-harbor trips on whichever meter is closest to its cap, so this tool tracks
each separately, anchored to its real reset time, and reports them side by side.

It is an ESTIMATE. It only sees Claude Code usage on this machine (not
claude.ai web, the API, or other devices), and the exact weighting Anthropic
applies toward each limit is not public, so each meter's scale is fixed by its
own calibration. Treat the numbers as a conservative early warning, and
re-calibrate (especially the session meter) when `/usage` drifts from them.

Commands:
  scan                       Weighted tokens per meter (and by model).
  set-reset <meter> <iso>    Anchor a meter's window to its real reset time
                             (from `/usage`), e.g. set-reset session 2026-07-09T00:50+02:00
  calibrate <meter> <pct>    Record "right now /usage shows <pct>% for <meter>".
  estimate                   Print every calibrated meter; exit 2 if any is over
                             its trigger.
  (no arg)                   estimate if calibrated, else scan.

Config: ~/.claude/safe-harbor.json
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
    "trigger_percent": 85.0,
    # Each meter: window length, its real reset time (ISO, from /usage; null = rolling),
    # and scope ("all" or a model-family substring like "fable").
    "meters": {
        "session":    {"length_hours": 5,   "reset": None, "scope": "all"},
        "week":       {"length_hours": 168, "reset": None, "scope": "all"},
        "week:fable": {"length_hours": 168, "reset": None, "scope": "fable"},
    },
    "component_weights": {"output": 5.0, "input": 1.0, "cache_creation": 1.25, "cache_read": 0.1},
    "model_weights": {"opus": 5.0, "fable": 5.0, "mythos": 5.0, "sonnet": 1.0, "haiku": 0.25, "default": 1.0},
    # meter -> list of {"at": iso, "reported_pct": float, "weighted": float}
    "calibrations": {},
}


def load_config():
    cfg = dict(DEFAULTS)
    if os.path.exists(CONFIG):
        try:
            cfg.update(json.loads(open(CONFIG, encoding="utf-8").read()))
        except Exception:
            pass
    if isinstance(cfg.get("calibrations"), list):  # migrate v2.0 single-list form
        cfg["calibrations"] = {"week": cfg["calibrations"]} if cfg["calibrations"] else {}
    cfg.setdefault("meters", DEFAULTS["meters"])
    return cfg


def save_config(cfg):
    open(CONFIG, "w", encoding="utf-8").write(json.dumps(cfg, indent=2, ensure_ascii=False))


def parse_ts(s):
    if not s:
        return None
    try:
        return datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except Exception:
        return None


def meter_start(meter_cfg, now):
    """Window start: anchored to the real reset if it's still in the future, else rolling."""
    length = timedelta(hours=meter_cfg.get("length_hours", 5))
    reset = parse_ts(meter_cfg.get("reset"))
    stale = False
    if reset is not None and reset > now:
        start = reset - length
    else:
        start = now - length  # rolling fallback (no reset set, or it already passed)
        stale = reset is not None
    return start, stale


def model_family(cfg, model):
    m = (model or "").lower()
    return next((k for k in cfg["model_weights"] if k != "default" and k in m), model or "unknown")


def model_weight(cfg, model):
    m = (model or "").lower()
    for key, w in cfg["model_weights"].items():
        if key != "default" and key in m:
            return w
    return cfg["model_weights"]["default"]


def scan(cfg):
    """Return {meter: {"weighted": float, "stale": bool, "byfam": {fam: w}}}."""
    now = datetime.now(timezone.utc)
    cw = cfg["component_weights"]
    meters = cfg["meters"]
    starts = {name: meter_start(mc, now) for name, mc in meters.items()}
    acc = {name: {"weighted": 0.0, "stale": starts[name][1], "byfam": {}} for name in meters}
    nfiles = 0
    for f in glob.glob(os.path.join(PROJECTS, "**", "*.jsonl"), recursive=True):
        nfiles += 1
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
            if ts is None:
                continue
            model = msg.get("model") or "unknown"
            fam = model_family(cfg, model)
            inp = u.get("input_tokens", 0) or 0
            o = u.get("output_tokens", 0) or 0
            cc = u.get("cache_creation_input_tokens", 0) or 0
            cr = u.get("cache_read_input_tokens", 0) or 0
            weighted = model_weight(cfg, model) * (
                o * cw["output"] + inp * cw["input"] + cc * cw["cache_creation"] + cr * cw["cache_read"]
            )
            for name, mc in meters.items():
                start = starts[name][0]
                if ts < start:
                    continue
                scope = mc.get("scope", "all")
                if scope != "all" and scope not in (model or "").lower():
                    continue
                acc[name]["weighted"] += weighted
                acc[name]["byfam"][fam] = acc[name]["byfam"].get(fam, 0.0) + weighted
    return acc, nfiles


def cmd_scan(cfg):
    acc, nfiles = scan(cfg)
    print(f"safe-harbor scan: {nfiles} transcript files")
    for name in cfg["meters"]:
        a = acc[name]
        tag = " (reset stale -> rolling)" if a["stale"] else ""
        print(f"  {name:14} weighted = {a['weighted']:>15,.0f}{tag}")
        for fam in sorted(a["byfam"], key=lambda k: -a["byfam"][k]):
            if a["byfam"][fam] > 0 and cfg["meters"][name].get("scope", "all") == "all":
                print(f"      {fam:10} {a['byfam'][fam]:>15,.0f}")
    return 0


def cmd_set_reset(cfg, meter, iso):
    if meter not in cfg["meters"]:
        print(f"Unknown meter '{meter}'. Known: {', '.join(cfg['meters'])}")
        return 1
    if parse_ts(iso) is None:
        print(f"Bad ISO time '{iso}'. Example: 2026-07-09T00:50+02:00")
        return 1
    cfg["meters"][meter]["reset"] = iso
    save_config(cfg)
    print(f"{meter} reset anchored to {iso}.")
    return 0


def cmd_calibrate(cfg, meter, percent):
    if meter not in cfg["meters"]:
        print(f"Unknown meter '{meter}'. Known: {', '.join(cfg['meters'])}")
        return 1
    acc, _ = scan(cfg)
    w = acc[meter]["weighted"]
    if w <= 0:
        print(f"No usage for '{meter}' in its window; cannot calibrate.")
        return 1
    cfg.setdefault("calibrations", {}).setdefault(meter, []).append({
        "at": datetime.now(timezone.utc).isoformat(),
        "reported_pct": float(percent),
        "weighted": w,
    })
    save_config(cfg)
    print(f"Calibrated {meter}: {percent}% == {w:,.0f} weighted tokens.")
    return 0


def cmd_estimate(cfg):
    cals = cfg.get("calibrations") or {}
    if not cals:
        print("Not calibrated. Run `scan`, then e.g.: calibrate session 69 / calibrate week 87")
        return 1
    acc, _ = scan(cfg)
    trig = cfg["trigger_percent"]
    rows, worst = [], 0.0
    for meter, points in cals.items():
        if not points or meter not in acc:
            continue
        cal = points[-1]
        factor = cal["reported_pct"] / cal["weighted"] if cal["weighted"] else 0
        est = acc[meter]["weighted"] * factor
        worst = max(worst, est)
        rows.append((meter, est, cal["reported_pct"], cal["at"][:16], acc[meter]["stale"]))
    print("safe-harbor estimate (per meter):")
    for meter, est, calpct, at, stale in sorted(rows, key=lambda r: -r[1]):
        flags = ("  <<< OVER" if est >= trig else "") + ("  [reset stale, recalibrate]" if stale else "")
        print(f"  {meter:14} ~{est:5.0f}%   (calibrated {at} at {calpct}%){flags}")
    if worst >= trig:
        print(f">>> Tightest meter ~{worst:.0f}% (trigger {trig}%): run safe-harbor and wrap up.")
        return 2
    print(f"Tightest meter ~{worst:.0f}%; ~{trig - worst:.0f} points of headroom.")
    return 0


def main():
    cfg = load_config()
    args = sys.argv[1:]
    if not args:
        return cmd_estimate(cfg) if cfg.get("calibrations") else cmd_scan(cfg)
    cmd = args[0]
    if cmd == "scan":
        return cmd_scan(cfg)
    if cmd == "set-reset" and len(args) >= 3:
        return cmd_set_reset(cfg, args[1], args[2])
    if cmd == "calibrate" and len(args) >= 3:
        return cmd_calibrate(cfg, args[1], args[2])
    if cmd == "estimate":
        return cmd_estimate(cfg)
    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main())
