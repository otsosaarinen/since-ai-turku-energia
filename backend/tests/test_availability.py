import numpy as np
import pandas as pd

from src.availability import AvailabilityIndex, rows_available_at

RNG = np.random.default_rng(0)
LOOKBACK_Q = 700  # quarter-hours


def random_origins(n: int, lo: str = "2026-06-05T00:00:00Z", hi: str = "2026-11-01T21:00:00Z") -> list[pd.Timestamp]:
    """n distinct random full-hour origins in [lo, hi] (fixed seed)."""
    hours = pd.date_range(lo, hi, freq="h")
    return list(hours[RNG.choice(len(hours), n, replace=False)])


def test_window_matches_reference_helper(long_data: pd.DataFrame, index: AvailabilityIndex, cfg: dict) -> None:
    """Fast index == organiser rows_available_at() on random origins (every cell)."""
    for o in random_origins(6):
        w = index.at(o, cfg["lookback_quarters"], cfg["horizon_steps"])
        ref = rows_available_at(long_data, o).reindex(w.index)
        for j, name in enumerate(w.columns):
            fast = w.values[:, j]
            slow = ref[name].to_numpy(dtype=float) if name in ref else np.full(len(fast), np.nan)
            assert np.allclose(fast, slow, equal_nan=True), (o, name)


def test_every_used_row_is_usable_at_origin(index: AvailabilityIndex, cfg: dict) -> None:
    for o in random_origins(40):
        w = index.at(o, cfg["lookback_quarters"], cfg["horizon_steps"])
        assert w.first_usable.max() <= o.value, o
        # present cells all carry a first_usable <= origin
        present = ~np.isnan(w.values)
        assert (w.first_usable[present] <= o.value).all()


def test_no_actuals_at_or_after_origin(index: AvailabilityIndex, cfg: dict) -> None:
    """Measured series can never be present for quarter-hours starting at/after the origin."""
    actual = [
        name
        for name in index.columns
        if name.startswith(("fi_imbalance", "fi_mfrr", "fi_afrr", "fi_consumption", "fi_production"))
        and not name.endswith("_fc_da")
    ] + ["fi_se3_flow", "fi_ee_flow"]
    for o in random_origins(40):
        w = index.at(o, cfg["lookback_quarters"], cfg["horizon_steps"])
        fut = slice(w.origin_row, None)
        for name in actual:
            assert np.isnan(w.col(name)[fut]).all(), (o, name)


def test_features_do_not_depend_on_rows_after_origin(long_data: pd.DataFrame) -> None:
    """Physically deleting every row with first_usable > origin leaves the window unchanged."""
    o = pd.Timestamp("2026-09-20T09:00:00Z")
    full = AvailabilityIndex(long_data)
    cut = AvailabilityIndex(long_data[long_data["first_usable_origin_utc"] <= o])
    wf = full.at(o, LOOKBACK_Q, 40)
    # the cut index may have a shorter grid end; compare on common timestamps
    wc = cut.at(o, LOOKBACK_Q, 40)
    assert wf.index.equals(wc.index) and wf.columns == wc.columns
    assert np.array_equal(wf.values, wc.values, equal_nan=True)


def test_labels_respect_cutoff(index: AvailabilityIndex) -> None:
    ts = pd.date_range("2026-09-06T00:00:00Z", periods=200, freq="15min")
    cutoff = pd.Timestamp("2026-09-06T21:00:00Z")
    y = index.labels(ts, "fi_imbalance_price", cutoff)
    rows = index.grid.get_indexer(ts)
    fu = index.F[rows, index.col_idx["fi_imbalance_price"]]
    assert np.isnan(y[fu > cutoff.value]).all()
    assert not np.isnan(y[fu <= cutoff.value]).any()
