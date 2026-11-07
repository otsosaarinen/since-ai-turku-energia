"""Post-processing experiments on the 8 rolling windows (one model fit per window, variants applied afterwards).
A: direction 'none' probability fixed to the training share. B: spike probabilities shifted in logit space by
(recent 14-day base rate - overall training base rate), with strength s in {0.5, 1}.
usage: uv run scripts/exp_postproc.py"""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "scripts"))
import numpy as np, pandas as pd  # noqa: E401
import run_rolling as rr
from src import predict, train

def logit(x): x = np.clip(x, 1e-4, 1 - 1e-4); return np.log(x / (1 - x))
def sig(z): return 1 / (1 + np.exp(-z))

cfg = train.load_config(); rr.cfg_margin = cfg["spike_margin"]
index = train.make_index(cfg); df = rr.global_frame(cfg, index)
res = {}
for st in rr.STARTS:
    tr = df[df["forecast_origin_utc"] + rr.LABEL_LAG <= st].reset_index(drop=True)
    ev = df[(df["forecast_origin_utc"] >= st) & (df["forecast_origin_utc"] < st + pd.Timedelta(days=7))].reset_index(drop=True)
    mdl = train.fit(tr, cfg, st, verbose=False)
    p = predict.predict_frame(mdl, ev, with_drivers=False)
    none_share = float((tr["dir"] == 0).mean())
    m = cfg["spike_margin"]
    rec = tr[tr["forecast_origin_utc"] >= st - pd.Timedelta(days=14) - rr.LABEL_LAG]
    var = {"base": p}
    q = p.copy(); q["p_none"] = none_share; s = (1 - none_share) / (q["p_up"] + q["p_down"]); q["p_up"] *= s; q["p_down"] *= s
    var["A_none_fixed"] = q
    for k, col, cond in (("hi", "p_spike_high", lambda d: d["y"] > d["spot_label"] + m), ("lo", "p_spike_low", lambda d: d["y"] < d["spot_label"] - m)):
        d = logit(cond(rec).mean()) - logit(cond(tr).mean())
        for s_ in (0.5, 1.0):
            var.setdefault(f"B_{s_}", p.copy())[col] = sig(logit(p[col].to_numpy()) + s_ * d)
    for name, pp in var.items():
        res.setdefault(name, []).append(rr.metrics(pp, ev))
    print(st, "none share", round(none_share, 4), flush=True)
base = pd.DataFrame(res["base"])
for name, r in res.items():
    r = pd.DataFrame(r)
    print(f"{name:14s} spike {r.brier_spike.mean():.4f} ({(r.brier_spike < base.brier_spike).sum()}/8 better, diff {(r.brier_spike - base.brier_spike).mean():+.5f})"
          f"  dir {r.brier_dir.mean():.4f} ({(r.brier_dir < base.brier_dir).sum()}/8, diff {(r.brier_dir - base.brier_dir).mean():+.5f})")
