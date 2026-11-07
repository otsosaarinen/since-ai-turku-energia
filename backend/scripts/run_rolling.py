"""Rolling-window validation: 8 weekly windows (10 Aug - 4 Oct), each trained ONLY on labels usable at the window start.

Features are built once per origin (they never depend on the cut-off) and cached; the training set of a window is
{origins o : o + 11 h <= window start}, which is exactly the set of origins whose 40 labels were published by then
(imbalance price is published 60 min after the quarter-hour ends, rounded up to the next full hour).
Evaluation rows are limited to delivery < 2026-10-04T21:00Z (no test-period actuals are ever read).

usage: uv run scripts/run_rolling.py [--tag NAME] [--ref TAG] [--set model.key=value ...]
"""

from __future__ import annotations

import argparse
import hashlib
import json

import numpy as np
import pandas as pd

from src import predict, train
from src.availability import AvailabilityIndex

ROOT = train.ROOT  # backend/: data, outputs and configs live below it
QUANTILE_LOW, QUANTILE_HIGH = 0.1, 0.9
WINDOW_DAYS = 7
CACHE_KEY_FILES = ("src/features.py", "src/availability.py")  # the cache is valid only for this feature code

LABEL_LAG = pd.Timedelta(hours=11)
END = pd.Timestamp("2026-10-04T21:00:00Z")
STARTS = [
    pd.Timestamp(x, tz="UTC")
    for x in (
        "2026-08-09T21:00",
        "2026-08-16T21:00",
        "2026-08-23T21:00",
        "2026-08-30T21:00",
        "2026-09-06T21:00",
        "2026-09-13T21:00",
        "2026-09-20T21:00",
        "2026-09-27T21:00",
    )
]
OUT = ROOT / "outputs" / "rolling"


def global_frame(cfg: dict, index: AvailabilityIndex) -> pd.DataFrame:
    """All origins with 40 labels known at the final cut-off (cached; key = hash of the feature code + data)."""
    digest = hashlib.sha1()
    for name in CACHE_KEY_FILES:
        digest.update((ROOT / name).read_bytes())
    digest.update(str((ROOT / cfg["paths"]["inputs"]).stat().st_mtime).encode())
    path = OUT / "cache" / f"frame_{digest.hexdigest()[:10]}.pkl"
    if path.exists():
        return pd.read_pickle(path)
    df = train.training_frame(index, cfg, END)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_pickle(path)
    return df


def metrics(pred: pd.DataFrame, df: pd.DataFrame, margin: float) -> dict[str, float]:
    """The five Level-1 metrics for one window (``margin`` = spike margin in EUR/MWh)."""
    y = df["y"].to_numpy()
    spot = df["spot_label"].to_numpy()

    def pinball(quantile_pred: np.ndarray, alpha: float) -> float:
        return np.mean(np.maximum(alpha * (y - quantile_pred), (alpha - 1) * (y - quantile_pred)))

    is_high, is_low = (y > spot + margin).astype(float), (y < spot - margin).astype(float)
    direction = df["dir"].to_numpy()
    onehot = np.column_stack([direction == 1, direction == -1, direction == 0]).astype(float)
    probs = np.column_stack([pred["p_up"], pred["p_down"], pred["p_none"]])
    pinball_mean = (pinball(pred["p10"].to_numpy(), QUANTILE_LOW) + pinball(pred["p90"].to_numpy(), QUANTILE_HIGH)) / 2
    brier_spike = (np.mean((pred["p_spike_high"] - is_high) ** 2) + np.mean((pred["p_spike_low"] - is_low) ** 2)) / 2
    return {
        "mae": float(np.mean(np.abs(pred["p50"] - y))),
        "pinball": float(pinball_mean),
        "coverage": float(np.mean((y >= pred["p10"]) & (y <= pred["p90"]))),
        "brier_spike": float(brier_spike),
        "brier_dir": float(np.mean(((probs - onehot) ** 2).sum(axis=1))),
    }


def main() -> None:
    """Run the 8 weekly windows, print per-window and mean metrics, save them and optionally compare to --ref."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--tag", default="rolling")
    parser.add_argument("--ref", default=None, help="tag of a previous run to compare with")
    parser.add_argument("--set", action="append")
    args = parser.parse_args()
    cfg = train.apply_overrides(train.load_config(), args.set)
    margin = cfg["spike_margin"]
    index = train.make_index(cfg)
    df = global_frame(cfg, index)
    rows = []
    for start in STARTS:
        tr = df[df["forecast_origin_utc"] + LABEL_LAG <= start]  # only origins whose 40 labels are published
        in_window = (df["forecast_origin_utc"] >= start) & (
            df["forecast_origin_utc"] < start + pd.Timedelta(days=WINDOW_DAYS)
        )
        ev = df[in_window]
        assert tr["delivery_start_utc"].max() < start, "training target after the window start"
        mdl = train.fit(tr.reset_index(drop=True), cfg, start, verbose=False)
        pred = predict.predict_frame(mdl, ev.reset_index(drop=True), with_drivers=False)
        r = metrics(pred, ev.reset_index(drop=True), margin)
        r.update(
            window=start.tz_convert("Europe/Helsinki").strftime("%d.%m."),
            n_train_origins=int(tr.forecast_origin_utc.nunique()),
        )
        rows.append(r)
        print(
            f"{r['window']}  train {r['n_train_origins']:4d}  mae {r['mae']:6.2f}  pin {r['pinball']:6.2f}  "
            f"cov {r['coverage']:.3f}  spike {r['brier_spike']:.4f}  dir {r['brier_dir']:.4f}",
            flush=True,
        )
    res = pd.DataFrame(rows)
    mean = res[["mae", "pinball", "coverage", "brier_spike", "brier_dir"]].mean()
    print("MEAN        " + "  ".join(f"{k} {v:.4f}" for k, v in mean.items()))
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{args.tag}.json").write_text(json.dumps({"rows": rows, "mean": mean.to_dict(), "set": args.set}))
    if args.ref and (OUT / f"{args.ref}.json").exists():
        ref = pd.DataFrame(json.loads((OUT / f"{args.ref}.json").read_text())["rows"])
        print(f"\nvs {args.ref}: mean diff (negative = better, except coverage) and #windows better")
        for k in ("mae", "pinball", "brier_spike", "brier_dir"):
            dlt = res[k] - ref[k]
            print(f"  {k:12s} {dlt.mean():+.4f}   better in {(dlt < 0).sum()}/{len(dlt)} windows")


if __name__ == "__main__":
    main()
