"""Data availability filter.

The binding rule of the challenge: at forecast origin t a row may be used only if
``first_usable_origin_utc <= t``.

* ``rows_available_at`` is the organiser's reference helper (copied verbatim in logic from
  starter_package_v1/baseline.ipynb). It is slow, so it is used in tests as the oracle.
* ``AvailabilityIndex`` is a fast, numpy implementation with identical semantics. It stores
  value and first-usable matrices on the quarter-hour grid and returns, for an origin, a
  window of values in which every cell that is not yet usable is NaN. Everything downstream
  (features) must read ONLY from this window; nothing touches the unfiltered table.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

QUARTER = pd.Timedelta(minutes=15)
_NAT_NS = np.iinfo(np.int64).max  # "never usable"


def to_utc(value) -> pd.Timestamp:
    ts = pd.Timestamp(value)
    return ts.tz_localize("UTC") if ts.tzinfo is None else ts.tz_convert("UTC")


def read_long(path: str | Path) -> pd.DataFrame:
    """Read a long-format file (parquet or csv) with UTC timestamps."""
    path = Path(path)
    df = pd.read_parquet(path) if path.suffix == ".parquet" else pd.read_csv(path, dtype={"dataset_id": str})
    for col in ("timestamp_utc", "first_usable_origin_utc"):
        df[col] = pd.to_datetime(df[col], utc=True)
    return df


def load_all(inputs_path: str | Path, spot_path: str | Path | None) -> pd.DataFrame:
    """Inputs plus (optionally) the Nord Pool spot series in one long table."""
    parts = [read_long(inputs_path)]
    if spot_path is not None and Path(spot_path).exists():
        parts.append(read_long(spot_path))
    return pd.concat(parts, ignore_index=True)


def rows_available_at(data: pd.DataFrame, origin_utc) -> pd.DataFrame:
    """Organiser reference: wide table of rows with first_usable_origin_utc <= origin."""
    origin = to_utc(origin_utc)
    usable = data.loc[data["first_usable_origin_utc"] <= origin]
    wide = usable.pivot(index="timestamp_utc", columns="series_id", values="value")
    return wide.sort_index()


@dataclass
class Window:
    """Availability-filtered view for one origin.

    ``values[r, s]`` is NaN unless the row was usable at ``origin``. Row ``origin_row``
    is the quarter-hour that starts at the origin (step 1). Rows before it are the past,
    rows ``origin_row .. origin_row + horizon - 1`` are the target quarter-hours.
    ``first_usable`` holds the (int64 ns) first_usable_origin_utc of every cell that is
    present, so the latest data actually used can be reported.
    """
    origin: pd.Timestamp
    index: pd.DatetimeIndex
    columns: list[str]
    values: np.ndarray
    first_usable: np.ndarray
    origin_row: int

    def col(self, name: str) -> np.ndarray:
        return self.values[:, self.columns.index(name)]


class AvailabilityIndex:
    def __init__(self, data: pd.DataFrame):
        if data.duplicated(["series_id", "timestamp_utc"]).any():
            raise ValueError("series_id + timestamp_utc must be unique")
        self.columns = sorted(data["series_id"].unique())
        t0, t1 = data["timestamp_utc"].min(), data["timestamp_utc"].max()
        self.grid = pd.date_range(t0, t1, freq=QUARTER, tz="UTC")
        n, s = len(self.grid), len(self.columns)
        self.V = np.full((n, s), np.nan)
        self.F = np.full((n, s), _NAT_NS, dtype=np.int64)
        r = self.grid.get_indexer(pd.DatetimeIndex(data["timestamp_utc"]))
        c = pd.Index(self.columns).get_indexer(data["series_id"])
        if (r < 0).any():
            raise ValueError("timestamps off the quarter-hour grid")
        self.V[r, c] = data["value"].to_numpy(dtype=float)
        # normalise to ns: pandas 3 may parse timestamps as us/s units
        self.F[r, c] = data["first_usable_origin_utc"].dt.as_unit("ns").astype("int64").to_numpy()
        self.col_idx = {c: i for i, c in enumerate(self.columns)}

    def row_of(self, ts) -> int:
        return int(self.grid.get_loc(to_utc(ts)))

    def at(self, origin_utc, lookback: int, horizon: int = 40) -> Window:
        """Window [origin-lookback, origin+horizon) with only cells usable at the origin."""
        origin = to_utc(origin_utc)
        ro = self.row_of(origin)
        lo = max(0, ro - lookback)
        hi = min(len(self.grid), ro + horizon)
        F = self.F[lo:hi]
        mask = F <= origin.value  # THE availability rule
        vals = np.where(mask, self.V[lo:hi], np.nan)
        fu = np.where(mask & ~np.isnan(vals), F, -1)
        return Window(origin, self.grid[lo:hi], self.columns, vals, fu, ro - lo)

    def labels(self, ts: pd.DatetimeIndex, series_id: str, known_at) -> np.ndarray:
        """Training labels: value at ``ts`` only if usable at ``known_at`` (else NaN).

        This is the only place where target-period values are read, and it applies the same
        first_usable filter against the *cut-off* origin (end of the training window).
        """
        k = to_utc(known_at).value
        r = self.grid.get_indexer(ts)
        c = self.col_idx[series_id]
        out = np.full(len(ts), np.nan)
        ok = r >= 0
        rr = r[ok]
        v = self.V[rr, c]
        v = np.where(self.F[rr, c] <= k, v, np.nan)
        out[ok] = v
        return out
