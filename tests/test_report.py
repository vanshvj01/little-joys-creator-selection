"""The report must say what the output tables say. Requires a prior `python run_all.py --no-tests`."""
import json
import re
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
import metrics as m  # noqa: E402

pytestmark = pytest.mark.skipif(not (m.OUT / "phase3_briefs.json").exists(), reason="run the pipeline first")


@pytest.fixture(scope="module")
def built():
    import report
    return report.build()


def test_effect_words():
    import report
    assert report.effect_words(0.6) == "40% cheaper"
    assert report.effect_words(1.5) == "50% more expensive"


def test_no_template_leftovers(built):
    _, html = built
    text = re.sub(r"<[^>]+>", " ", html)
    assert "{{" not in html and "{%" not in html
    assert not re.search(r"\bnan\b|\bNone\b", text)


def test_top_five_in_brief_order(built):
    ctx, html = built
    handles = [b["handle"] for b in json.loads((m.OUT / "phase3_briefs.json").read_text(encoding="utf-8"))]
    positions = [html.index(f"<h3>@{h}</h3>") for h in handles]
    assert positions == sorted(positions) and len(handles) == 5


def test_headline_numbers_match_sources(built):
    ctx, html = built
    import report
    ads = m.load_ads()
    assert report.inr(m.pooled(ads)["cpa"]) == ctx["facts"]["account_cpa"]
    w = pd.read_csv(m.OUT / "phase1_winning_ingredients.csv").iloc[0]
    assert report.effect_words(w.cpa_ratio_adjusted) in html
    agree = pd.read_csv(m.OUT / "phase1_label_agreement.csv").set_index("label").loc["ALL"]
    assert f"{int(agree.agree)} of {int(agree.checked)}" in html


def test_every_brief_citation_exists():
    ads = set(pd.read_csv(m.DATA / "ads.csv").ad_id)
    posts = set(pd.read_csv(m.DATA / "creator_posts.csv").post_url)
    for b in json.loads((m.OUT / "phase3_briefs.json").read_text(encoding="utf-8")):
        assert {a["ad_id"] for a in b["ad_refs"]} <= ads
        assert set(b["post_refs"]) <= posts
