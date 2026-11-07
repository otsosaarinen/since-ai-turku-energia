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
DEFAULT_HORIZON = 40  # target quarter-hours per origin (10 h)
_NAT_NS = np.iinfo(np.int64).max  # "never usable"


def to_utc(value: pd.Timestamp | str | np.datetime64) -> pd.Timestamp:
    """Timestamp in UTC: naive input is taken as UTC, aware input is converted."""
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


def rows_available_at(data: pd.DataFrame, origin_utc: pd.Timestamp | str) -> pd.DataFrame:
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
        """Values of one series over the window (NaN where not usable at the origin)."""
        return self.values[:, self.columns.index(name)]


class AvailabilityIndex:
    """Quarter-hour grid of values and first-usable times; the only gateway to the data for features and labels."""

    def __init__(self, data: pd.DataFrame) -> None:
        if data.duplicated(["series_id", "timestamp_utc"]).any():
            raise ValueError("series_id + timestamp_utc must be unique")
        self.columns = sorted(data["series_id"].unique())
        t0, t1 = data["timestamp_utc"].min(), data["timestamp_utc"].max()
        self.grid = pd.date_range(t0, t1, freq=QUARTER, tz="UTC")
        n_rows, n_series = len(self.grid), len(self.columns)
        self.V = np.full((n_rows, n_series), np.nan)  # values
        self.F = np.full((n_rows, n_series), _NAT_NS, dtype=np.int64)  # first usable origin, int64 ns
        rows = self.grid.get_indexer(pd.DatetimeIndex(data["timestamp_utc"]))
        cols = pd.Index(self.columns).get_indexer(data["series_id"])
        if (rows < 0).any():
            raise ValueError("timestamps off the quarter-hour grid")
        self.V[rows, cols] = data["value"].to_numpy(dtype=float)
        # normalise to ns: pandas 3 may parse timestamps as us/s units
        self.F[rows, cols] = data["first_usable_origin_utc"].dt.as_unit("ns").astype("int64").to_numpy()
        self.col_idx = {name: i for i, name in enumerate(self.columns)}

    def row_of(self, ts: pd.Timestamp | str) -> int:
        """Grid row of a quarter-hour timestamp."""
        return int(self.grid.get_loc(to_utc(ts)))

    def at(self, origin_utc: pd.Timestamp | str, lookback: int, horizon: int = DEFAULT_HORIZON) -> Window:
        """Window [origin-lookback, origin+horizon) with only cells usable at the origin."""
        origin = to_utc(origin_utc)
        origin_row = self.row_of(origin)
        lo = max(0, origin_row - lookback)
        hi = min(len(self.grid), origin_row + horizon)
        first_usable = self.F[lo:hi]
        usable = first_usable <= origin.value  # THE availability rule: first_usable_origin_utc <= origin
        values = np.where(usable, self.V[lo:hi], np.nan)
        used_first_usable = np.where(usable & ~np.isnan(values), first_usable, -1)
        return Window(origin, self.grid[lo:hi], self.columns, values, used_first_usable, origin_row - lo)

    def labels(self, ts: pd.DatetimeIndex, series_id: str, known_at: pd.Timestamp | str) -> np.ndarray:
        """Training labels: value at ``ts`` only if usable at ``known_at`` (else NaN).

        This is the only place where target-period values are read, and it applies the same
        first_usable filter against the *cut-off* origin (end of the training window).
        """
        known_ns = to_utc(known_at).value
        rows = self.grid.get_indexer(ts)
        col = self.col_idx[series_id]
        out = np.full(len(ts), np.nan)
        on_grid = rows >= 0
        grid_rows = rows[on_grid]
        values = self.V[grid_rows, col]
        out[on_grid] = np.where(self.F[grid_rows, col] <= known_ns, values, np.nan)
        return out
