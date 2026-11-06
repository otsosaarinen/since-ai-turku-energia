"""Rolling-window validation: 8 weekly windows (10 Aug - 4 Oct), each trained ONLY on labels usable at the window start.

Features are built once per origin (they never depend on the cut-off) and cached; the training set of a window is
{origins o : o + 11 h <= window start}, which is exactly the set of origins whose 40 labels were published by then
(imbalance price is published 60 min after the quarter-hour ends, rounded up to the next full hour).
Evaluation rows are limited to delivery < 2026-10-04T21:00Z (no test-period actuals are ever read).

usage: uv run scripts/run_rolling.py [--tag NAME] [--ref TAG] [--set model.key=value ...]
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import yaml  # noqa: E402

from src import predict, train  # noqa: E402

LABEL_LAG = pd.Timedelta(hours=11)
END = pd.Timestamp("2026-10-04T21:00:00Z")
STARTS = [pd.Timestamp(x, tz="UTC") for x in
          ("2026-08-09T21:00", "2026-08-16T21:00", "2026-08-23T21:00", "2026-08-30T21:00",
           "2026-09-06T21:00", "2026-09-13T21:00", "2026-09-20T21:00", "2026-09-27T21:00")]
OUT = ROOT / "outputs" / "rolling"


def global_frame(cfg, index):
    """All origins with 40 labels known at the final cut-off (cached; key = hash of the feature code + data)."""
    h = hashlib.sha1()
    for f in ("src/features.py", "src/availability.py"):
        h.update((ROOT / f).read_bytes())
    h.update(str((ROOT / cfg["paths"]["inputs"]).stat().st_mtime).encode())
    path = OUT / "cache" / f"frame_{h.hexdigest()[:10]}.pkl"
    if path.exists():
        return pd.read_pickle(path)
    df = train.training_frame(index, cfg, END)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_pickle(path)
    return df


def metrics(p, df):
    y, m = df["y"].to_numpy(), cfg_margin
    sp = df["spot_label"].to_numpy()
    pin = lambda q, a: np.mean(np.maximum(a * (y - q), (a - 1) * (y - q)))  # noqa: E731
    hi, lo = (y > sp + m).astype(float), (y < sp - m).astype(float)
    d = df["dir"].to_numpy()
    onehot = np.column_stack([d == 1, d == -1, d == 0]).astype(float)
    pr = np.column_stack([p["p_up"], p["p_down"], p["p_none"]])
    return {
        "mae": float(np.mean(np.abs(p["p50"] - y))),
        "pinball": float((pin(p["p10"].to_numpy(), 0.1) + pin(p["p90"].to_numpy(), 0.9)) / 2),
        "coverage": float(np.mean((y >= p["p10"]) & (y <= p["p90"]))),
        "brier_spike": float((np.mean((p["p_spike_high"] - hi) ** 2) + np.mean((p["p_spike_low"] - lo) ** 2)) / 2),
        "brier_dir": float(np.mean(((pr - onehot) ** 2).sum(axis=1))),
    }


def main():
    global cfg_margin
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="rolling")
    ap.add_argument("--ref", default=None, help="tag of a previous run to compare with")
    ap.add_argument("--set", action="append")
    a = ap.parse_args()
    cfg = train.load_config()
    for s in a.set or []:
        k, v = s.split("=", 1)
        d = cfg
        for part in k.split(".")[:-1]:
            d = d[part]
        d[k.split(".")[-1]] = yaml.safe_load(v)
    cfg_margin = cfg["spike_margin"]
    index = train.make_index(cfg)
    df = global_frame(cfg, index)
    rows = []
    for st in STARTS:
        tr = df[df["forecast_origin_utc"] + LABEL_LAG <= st]
        ev = df[(df["forecast_origin_utc"] >= st) & (df["forecast_origin_utc"] < st + pd.Timedelta(days=7))]
        assert tr["delivery_start_utc"].max() < st, "training target after the window start"
        mdl = train.fit(tr.reset_index(drop=True), cfg, st, verbose=False)
        p = predict.predict_frame(mdl, ev.reset_index(drop=True), with_drivers=False)
        r = metrics(p, ev.reset_index(drop=True))
        r.update(window=st.tz_convert("Europe/Helsinki").strftime("%d.%m."), n_train_origins=int(tr.forecast_origin_utc.nunique()))
        rows.append(r)
        print(f"{r['window']}  train {r['n_train_origins']:4d}  mae {r['mae']:6.2f}  pin {r['pinball']:6.2f}  cov {r['coverage']:.3f}  "
              f"spike {r['brier_spike']:.4f}  dir {r['brier_dir']:.4f}", flush=True)
    res = pd.DataFrame(rows)
    mean = res[["mae", "pinball", "coverage", "brier_spike", "brier_dir"]].mean()
    print("MEAN        " + "  ".join(f"{k} {v:.4f}" for k, v in mean.items()))
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{a.tag}.json").write_text(json.dumps({"rows": rows, "mean": mean.to_dict(), "set": a.set}))
    if a.ref and (OUT / f"{a.ref}.json").exists():
        ref = pd.DataFrame(json.loads((OUT / f"{a.ref}.json").read_text())["rows"])
        print(f"\nvs {a.ref}: mean diff (negative = better, except coverage) and #windows better")
        for k in ("mae", "pinball", "brier_spike", "brier_dir"):
            dlt = res[k] - ref[k]
            print(f"  {k:12s} {dlt.mean():+.4f}   better in {(dlt < 0).sum()}/{len(dlt)} windows")


if __name__ == "__main__":
    main()
