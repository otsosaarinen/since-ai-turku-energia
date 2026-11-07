"""The fixed questions the website may ask. The browser sends only a preset id, never text: a run executes model-written
Python, so free text from a web page must never reach the model.
"""

from datetime import UTC, datetime

from .sources import iso_utc

# The prompts live here, not in the browser. "key" names the API key a preset cannot run without.
PRESETS = {
    "imbalance": {
        "label": "Imbalance price, 24 h + 10 d",
        "key": "FINGRID_API_KEY",  # the run cannot fetch the imbalance prices without it
        "about": (
            "Hourly for the next 24 hours, then one row a day for the next 10 days. Each hour's day-ahead spot "
            "price plus the live grid balance (production surplus/deficit, wind output) and the recent spread of "
            "real imbalance prices."
        ),
        # one entry per sentence group so the steps can be read (and changed) one by one
        "prompt": " ".join(
            [
                "Forecast the Finnish imbalance price hourly for the next 24 hours (24 rows, starting at the next "
                "full hour) and then daily for the next 10 days (10 rows, one at 12:00 UTC each day, starting "
                "tomorrow): 34 rows in all, 24 of them hourly.",
                "The imbalance price follows the live grid balance, so use the live sources, not only history.",
                "Follow these steps exactly.",
                "1) get_data nordpool_price with start = 24 hours ago (leave end out): the Finland spot price in "
                "EUR/MWh for the last 24 hours (realised) and for every hour already published ahead (the "
                "day-ahead prices, which are known). This is the market's own level for each hour. Also get_data "
                "spot_price_fi as a cross-check of the current price: use its PriceNoTax field (EUR/kWh, multiply "
                "by 1000 for EUR/MWh, e.g. 0.00586 EUR/kWh = 5.86 EUR/MWh), never PriceWithTax, because imbalance "
                "prices carry no tax.",
                "2) get_data fingrid_imbalance_price with start = 5 hours ago and end = now (ISO8601 UTC): you get "
                "about 20 quarter-hour prices.",
                "3) get_data fingrid_surplus and get_data fingrid_wind_gen with start = 2 hours ago and end = now: "
                "the live production surplus/deficit in MW (negative = Finland is short of power) and the live wind "
                "production. Also get_data fingrid_consumption for the same window (live demand).",
                "4) With run_python read the saved files: pair each recent imbalance price with the realised Finland "
                "spot price of the same quarter-hour and compute spread = imbalance price minus spot, then its median, "
                "10th and 90th percentile. Then correct the median by the live balance: a production deficit "
                "(negative surplus) or falling wind production means the grid needs more power, so raise the "
                "spread; a surplus or rising wind means it needs less, so lower it. State the shift you applied and "
                "the live values with their timestamps.",
                "5) Hourly rows: for each hour take that hour's own Finland spot price from step 1 (the published "
                "day-ahead price; if an hour is not published yet, use the last published one and say so). "
                "forecast = that hour's spot + the corrected spread; low = spot + 10th percentile spread; high = "
                "spot + 90th percentile spread. The hourly forecasts must follow the shape of the spot prices, not "
                "be one flat number. Daily rows: there is no price that far out, so give each day as a trend with a "
                "range (around the average spot level of the published hours) and say in one line that it is a "
                "trend, not a priced forecast. Do NOT extrapolate a trend line. Clamp all values to -50..400 "
                "EUR/MWh.",
                "6) End with the csv block, metric=imbalance_price, horizon=24h on the hourly rows and horizon=10d "
                "on the daily rows. In drivers give the reason behind each row's number in one line: the source and "
                "its live value with the timestamp, the shift you applied and which way it moved the number. Join "
                "the parts with ' ; ' and put no comma inside drivers (it is the last csv field). Keep the prose "
                "explanation under 10 lines and name the live source that moved your number. Only use hours later "
                "than the current time.",
            ]
        ),
    },
    "dayahead": {
        "label": "Day-ahead price, next 12 h",
        "about": ("Lists the published day-ahead prices of the next hours. No forecasting."),
        "prompt": (
            "Get nordpool_price and list the Finland day-ahead price for every 2 hours of the next 12 hours "
            "starting at the next full hour. Do not invent any numbers. Only list hours later than the current "
            "time. End with the csv block inside a ```csv code fence, horizon=12h, metric=spot_price, "
            "low=high=value, drivers=nordpool_price."
        ),
    },
}


def with_context(prompt: str, now: datetime | None = None) -> str:
    """Prefix the prompt with the real time and time format: small models do not know the time and pass 'now'."""
    stamp = iso_utc(now or datetime.now(UTC))
    return (
        f"Current time (UTC): {stamp}. In get_data params always use ISO8601 UTC timestamps such as {stamp}, "
        "never words like 'now' or '5 hours ago' (compute them from the current time above). "
        "Only forecast hours later than the current time. "
        "Put the csv table inside a ```csv code fence, with times as ISO8601 UTC.\n\n" + prompt
    )
