import copy

import pandas as pd

from src import predict, train
from src.availability import AvailabilityIndex
from src.features import TOGGLE_GROUPS, build_dataset, dropped_features, feature_columns


def test_toggle_groups_remove_exactly_their_features(index: AvailabilityIndex, cfg: dict) -> None:
    df = build_dataset(index, [pd.Timestamp("2026-09-20T09:00:00Z")], cfg)
    cols = feature_columns(df)
    assert dropped_features(cols, []) == []
    expect = {"solar": ("solar_", "resload_"), "wind": ("wind_", "resload_"), "consumption": ("cons_fc", "resload_")}
    for group, prefixes in expect.items():
        assert set(dropped_features(cols, [group])) == {c for c in cols if c.startswith(prefixes)}, group
        assert dropped_features(cols, [group])  # each group really owns some features
    everything = dropped_features(cols, list(TOGGLE_GROUPS))
    assert set(everything) == {c for c in cols if c.startswith(("solar_", "wind_", "cons_fc", "resload_"))}
    # nothing else is touched: spot, imbalance history and measured consumption stay
    for kept in ("spot_t", "imb_last", "cons_last", "prod_last", "dir_last"):
        assert kept in cols and kept not in everything


def test_fit_leaves_out_switched_off_features(index: AvailabilityIndex, cfg: dict) -> None:
    cfg2 = copy.deepcopy(cfg)
    cfg2["model"].update(rounds_max=8, early_stopping=3, n_seeds=1)
    cfg2["model"]["drop_features"] = ["solar_t", "solar_hmean"]
    cutoff = pd.Timestamp("2026-08-30T21:00:00Z")
    origins = pd.date_range("2026-08-02T00:00:00Z", "2026-08-30T10:00:00Z", freq="3h")
    df = build_dataset(index, origins, cfg2, label_cutoff=cutoff)
    mdl = train.fit(df, cfg2, cutoff, verbose=False)
    assert "solar_t" not in mdl.features and "solar_hmean" not in mdl.features
    assert "solar_t_chg1d" in mdl.features  # only the listed ones are removed
    out = predict.predict_frame(mdl, df.head(40), with_drivers=False)  # prediction works on the reduced feature set
    assert len(out) == 40 and (out["p10"] <= out["p50"]).all() and (out["p50"] <= out["p90"]).all()
