from datetime import date

from PIL import Image

from app.agents.report_catalog import MARKET_REPORT_SLOTS
from app.agents.report_render import build_indicator_views, render_market_report_image


def test_market_report_catalog_has_21_unique_slots():
    positions = [slot.position for slot in MARKET_REPORT_SLOTS]

    assert len(MARKET_REPORT_SLOTS) == 21
    assert positions == list(range(1, 22))
    assert len({slot.indicator_id for slot in MARKET_REPORT_SLOTS}) == 21


def test_build_indicator_views_maps_values_and_missing_slots():
    views = build_indicator_views(
        [
            {
                "indicator_id": "kospi",
                "name": "코스피",
                "value": 2650.25,
                "prev": 2600.25,
                "change_pct": 1.92,
                "unit": "pt",
                "source": "fixture",
            }
        ],
        missing_indicators=["kosdaq"],
    )

    assert len(views) == 21
    kospi = views[0]
    assert kospi["display_name"] == "코스피"
    assert kospi["current_value"] == 2650.25
    assert kospi["change_value"] == 50.0
    assert kospi["change_percent"] == 1.92
    assert kospi["direction"] == "up"

    kosdaq = views[1]
    assert kosdaq["display_name"] == "코스닥"
    assert kosdaq["missing"] is True
    assert kosdaq["direction"] == "flat"


def test_render_market_report_image_creates_1080_png(tmp_path):
    out_path = tmp_path / "market_report_20260710.png"
    indicators = [
        {
            "indicator_id": "kospi",
            "name": "코스피",
            "value": 2650.25,
            "prev": 2600.25,
            "change_pct": 1.92,
            "unit": "pt",
            "source": "fixture",
        },
        {
            "indicator_id": "btc",
            "name": "비트코인",
            "value": 63138.0,
            "prev": 62087.99,
            "change_pct": 1.69,
            "unit": "USD",
            "source": "fixture",
        },
    ]

    result = render_market_report_image(
        indicators,
        run_date=date(2026, 7, 10),
        out_path=out_path,
        missing_indicators=["silver"],
    )

    assert result == str(out_path)
    with Image.open(out_path) as image:
        assert image.format == "PNG"
        assert image.size == (1080, 1080)
        assert image.mode == "RGB"
