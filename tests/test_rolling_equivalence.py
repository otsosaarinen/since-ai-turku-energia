import pandas as pd

from src import train
from src.availability import AvailabilityIndex

LABEL_LAG = pd.Timedelta(hours=11)


def test_filtered_global_frame_equals_frame_built_at_cutoff(long_data, cfg):
    """The rolling script's shortcut (one frame, origins with o+11h <= cutoff) == training_frame(cutoff)."""
    index = AvailabilityIndex(long_data)
    final = pd.Timestamp("2026-10-04T21:00:00Z")
    cutoff = pd.Timestamp("2026-08-30T21:00:00Z")
    glob = train.training_frame(index, cfg, final)
    direct = train.training_frame(index, cfg, cutoff)
    sub = glob[glob["forecast_origin_utc"] + LABEL_LAG <= cutoff].reset_index(drop=True)
    pd.testing.assert_frame_equal(sub, direct.reset_index(drop=True), check_exact=True)
    assert direct["delivery_start_utc"].max() < cutoff
