import numpy as np
import pandas as pd
import pytest

from src.availability import AvailabilityIndex
from src.features import build_dataset, build_origin_features, data_cutoff, feature_columns

ORIGINS = [pd.Timestamp(x) for x in ("2026-07-03T05:00:00Z", "2026-09-06T21:00:00Z", "2026-10-04T21:00:00Z",
                                      "2026-10-26T03:00:00Z", "2026-11-01T21:00:00Z")]


def feats(index, o, cfg):
    return build_origin_features(index.at(o, cfg["lookback_quarters"], cfg["horizon_steps"]), cfg["horizon_steps"])


@pytest.mark.parametrize("o", ORIGINS)
def test_cutoff_never_after_origin(index, cfg, o):
    w = index.at(o, cfg["lookback_quarters"], cfg["horizon_steps"])
    assert data_cutoff(w) <= o


@pytest.mark.parametrize("o", ORIGINS)
def test_features_identical_when_rows_after_origin_are_removed(long_data, index, cfg, o):
    """Recompute with every row that was not yet usable physically deleted: no change."""
    cut = AvailabilityIndex(long_data[long_data["first_usable_origin_utc"] <= o])
    a, b = feats(index, o, cfg), feats(cut, o, cfg)
    pd.testing.assert_frame_equal(a, b, check_exact=True)


@pytest.mark.parametrize("o", ORIGINS[:3])
def test_features_identical_when_future_rows_are_corrupted(long_data, cfg, index, o):
    """Replace the values of all not-yet-usable rows by garbage: features must not move."""
    bad = long_data.copy()
    m = bad["first_usable_origin_utc"] > o
    bad.loc[m, "value"] = 123456.789
    a, b = feats(index, o, cfg), feats(AvailabilityIndex(bad), o, cfg)
    pd.testing.assert_frame_equal(a, b, check_exact=True)


def test_training_labels_only_from_known_rows(index, cfg):
    cutoff = pd.Timestamp("2026-09-06T21:00:00Z")
    origins = pd.date_range("2026-08-30T00:00:00Z", "2026-09-06T21:00:00Z", freq="h")
    df = build_dataset(index, origins, cfg, label_cutoff=cutoff)
    assert len(df) > 0
    # every target quarter-hour's label was published by the cut-off
    r = index.grid.get_indexer(pd.DatetimeIndex(df["delivery_start_utc"]))
    fu = index.F[r, index.col_idx["fi_imbalance_price"]]
    assert (fu <= cutoff.value).all()
    # all 40 steps present for every kept origin
    assert (df.groupby("forecast_origin_utc").size() == cfg["horizon_steps"]).all()
    assert df["forecast_origin_utc"].max() <= cutoff - pd.Timedelta(hours=10)


def test_no_label_or_target_column_is_a_feature(index, cfg):
    df = build_dataset(index, [ORIGINS[0]], cfg, label_cutoff=pd.Timestamp("2026-09-06T21:00:00Z"))
    fc = feature_columns(df)
    assert not {"y", "dir", "spot_label"} & set(fc)
