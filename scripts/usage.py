#!/usr/bin/env python3
"""safe-harbor usage estimator (multi-meter, self-anchoring).

Estimates how close you are to each of your Claude subscription limits, from
inside a session, by summing the token usage recorded in your local Claude
Code transcripts and scaling each meter against a figure you calibrate from
the real `/usage` reading.

Claude enforces several limits at once, each with its own window:
  - the SESSION window (~5h). It is NOT a fixed clock reset: it starts with the
    first message you send after the previous window expired, and runs 5h from
    there. Under continuous use each window starts right as the last one ends;
    after an idle gap the next one starts whenever you next message. This tool
    reconstructs that window from your transcript timestamps, so it needs no
    reset time from you.
  - the WEEKLY window, anchored to a fixed reset time you give it once (it then
    rolls forward on its own).
safe-harbor trips on whichever meter is closest to its cap.

It is an ESTIMATE. It only sees Claude Code usage on this machine (not
claude.ai web, the API, or other devices), and the exact weighting Anthropic
applies toward each limit is not public, so each meter's scale is fixed by its
own calibration. The token counting itself is exact (it matches Claude Code's
own stats-cache to the token). Treat the percents as a conservative early
warning, not a precise gauge.

Commands:
  scan                       Weighted tokens per meter, with its window.
  set-reset <meter> <iso>    Set a reset-anchored meter's reset time (from
                             `/usage`), e.g. set-reset week 2026-07-12T02:00+02:00
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
    # Each meter: length_hours, anchor ("gap" self-computes the window from
    # message timestamps; "reset" anchors to a fixed reset that rolls forward),
    # reset (ISO, only for anchor "reset"), and scope ("all" or a model substring).
    "meters": {
        "session": {"length_hours": 5,   "anchor": "gap",   "scope": "all"},
        "week":    {"length_hours": 168, "anchor": "reset", "reset": None, "scope": "all"},
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
    if isinstance(cfg.get("calibrations"), list):
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


def model_family(cfg, model):
    m = (model or "").lower()
    return next((k for k in cfg["model_weights"] if k != "default" and k in m), model or "unknown")


def model_weight(cfg, model):
    m = (model or "").lower()
    for key, w in cfg["model_weights"].items():
        if key != "default" and key in m:
            return w
    return cfg["model_weights"]["default"]


def read_records(cfg):
    """One pass over every transcript: list of (ts, family, weighted)."""
    cw = cfg["component_weights"]
    recs = []
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
            weighted = model_weight(cfg, model) * (
                (u.get("output_tokens", 0) or 0) * cw["output"]
                + (u.get("input_tokens", 0) or 0) * cw["input"]
                + (u.get("cache_creation_input_tokens", 0) or 0) * cw["cache_creation"]
                + (u.get("cache_read_input_tokens", 0) or 0) * cw["cache_read"]
            )
            recs.append((ts, model_family(cfg, model), weighted, (model or "").lower()))
    return recs, nfiles


def gap_window_start(all_ts, length):
    """Current window start: a new window begins at the first message whose
    timestamp is >= previous window start + length. Message-triggered, so an
    idle gap pushes the next start to whenever activity resumes (no auto-reset)."""
    start = None
    for t in sorted(all_ts):
        if start is None or t >= start + length:
            start = t
    return start


def meter_window(cfg, name, all_ts, now):
    mc = cfg["meters"][name]
    length = timedelta(hours=mc.get("length_hours", 5))
    anchor = mc.get("anchor", "reset")
    if anchor == "gap":
        start = gap_window_start(all_ts, length)
        active = start is not None and now < start + length
        return (start if active else now), active  # inactive -> empty pending window
    reset = parse_ts(mc.get("reset"))
    if reset is None:
        return now - length, True  # no reset known: rolling fallback
    while reset <= now:
        reset += length
    return reset - length, True


def scan(cfg):
    recs, nfiles = read_records(cfg)
    now = datetime.now(timezone.utc)
    all_ts = [r[0] for r in recs]
    acc = {}
    for name, mc in cfg["meters"].items():
        start, active = meter_window(cfg, name, all_ts, now)
        scope = mc.get("scope", "all")
        total = 0.0
        byfam = {}
        if active:
            for ts, fam, w, modl in recs:
                if ts < start:
                    continue
                if scope != "all" and scope not in modl:
                    continue
                total += w
                byfam[fam] = byfam.get(fam, 0.0) + w
        acc[name] = {"weighted": total, "start": start, "active": active, "byfam": byfam}
    return acc, nfiles, now


def cmd_scan(cfg):
    acc, nfiles, now = scan(cfg)
    print(f"safe-harbor scan: {nfiles} transcript files, now {now.isoformat()[:19]}Z")
    for name in cfg["meters"]:
        a = acc[name]
        win = f"since {a['start'].astimezone(timezone.utc).isoformat()[:19]}Z" if a["active"] else "window empty (between sessions)"
        print(f"  {name:10} weighted = {a['weighted']:>15,.0f}   [{win}]")
        for fam in sorted(a["byfam"], key=lambda k: -a["byfam"][k]):
            if a["byfam"][fam] > 0 and cfg["meters"][name].get("scope", "all") == "all":
                print(f"      {fam:10} {a['byfam'][fam]:>15,.0f}")
    return 0


def cmd_set_reset(cfg, meter, iso):
    if meter not in cfg["meters"]:
        print(f"Unknown meter '{meter}'. Known: {', '.join(cfg['meters'])}")
        return 1
    if parse_ts(iso) is None:
        print(f"Bad ISO time '{iso}'. Example: 2026-07-12T02:00+02:00")
        return 1
    cfg["meters"][meter]["anchor"] = "reset"
    cfg["meters"][meter]["reset"] = iso
    save_config(cfg)
    print(f"{meter} reset anchored to {iso}.")
    return 0


def cmd_calibrate(cfg, meter, percent):
    if meter not in cfg["meters"]:
        print(f"Unknown meter '{meter}'. Known: {', '.join(cfg['meters'])}")
        return 1
    acc, _, _ = scan(cfg)
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
    acc, _, _ = scan(cfg)
    trig = cfg["trigger_percent"]
    rows, worst = [], 0.0
    for meter, points in cals.items():
        if not points or meter not in acc:
            continue
        cal = points[-1]
        factor = cal["reported_pct"] / cal["weighted"] if cal["weighted"] else 0
        est = acc[meter]["weighted"] * factor
        worst = max(worst, est)
        rows.append((meter, est, cal["reported_pct"], cal["at"][:16], acc[meter]["active"]))
    print("safe-harbor estimate (per meter):")
    for meter, est, calpct, at, active in sorted(rows, key=lambda r: -r[1]):
        flag = "  <<< OVER" if est >= trig else ("  [window empty]" if not active else "")
        print(f"  {meter:10} ~{est:5.0f}%   (calibrated {at} at {calpct}%){flag}")
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
