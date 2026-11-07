"""The fixed questions: they must name sources that exist and say which spot-price field to use."""

import pytest

pytest.importorskip("openai")  # the `harness` dependency group

import re  # noqa: E402

from harness.presets import PRESETS  # noqa: E402
from harness.sources import SOURCES  # noqa: E402


@pytest.mark.parametrize("preset_id", sorted(PRESETS))
def test_every_get_data_source_in_a_prompt_exists(preset_id):
    prompt = PRESETS[preset_id]["prompt"]
    named = set(re.findall(r"get_data (\w+)", prompt)) | set(re.findall(r"\b(nordpool_price|spot_price_fi)\b", prompt))
    assert named, "the prompt should name at least one source"
    assert named <= set(SOURCES), f"unknown sources in the {preset_id} prompt: {named - set(SOURCES)}"


def test_the_imbalance_prompt_uses_the_untaxed_spot_price():
    prompt = PRESETS["imbalance"]["prompt"]
    assert "PriceNoTax" in prompt and "never PriceWithTax" in prompt


def test_the_realised_spot_window_is_a_window_the_source_understands():
    # the prompt asks get_data nordpool_price for start/end: the source must have both placeholders
    assert "{start}" in SOURCES["nordpool_price"]["url"] and "{end}" in SOURCES["nordpool_price"]["url"]
