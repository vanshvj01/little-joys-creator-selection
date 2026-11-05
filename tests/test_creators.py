import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
import phase2_creators as c  # noqa: E402


def toy_posts():
    return pd.DataFrame({
        "creator_id": ["A", "A", "B"], "post_url": ["1", "2", "3"],
        "posted_on": pd.to_datetime(["2026-10-01", "2026-05-01", "2026-10-01"]),
        "plays": [1000.0, 1000.0, np.nan], "likes": [3, 100, 50], "comments": [10, 10, 1], "reshares": [5, 5, 0],
        "topic": ["", "", ""], "what_stands_out": ["", "", ""], "caption": ["", "", ""], "transcript": [None, None, None],
        "children_on_camera": ["yes", "no", "yes"], "child_ages": ["3-7", None, "0-2"],
        "presenter_age": ["3-7", "25-34", "25-34"], "content_type": ["lifestyle"] * 3,
        "is_sponsored": ["yes", "no", "yes"], "transcript_language": [None, None, None],
        "brands_visible": ["Gritzo", "Gritzo", None],
    })


def test_hidden_likes_are_excluded_not_penalised():
    p = c.post_features(toy_posts())
    assert p.likes_hidden.tolist() == [True, False, False]
    assert np.isnan(p.like_rate[0])            # hidden: no like rate, rather than a near-zero one
    assert p.like_rate[1] == 0.1
    assert p.talk_rate[0] == 0.015             # comments + reshares still count for the hidden-like post


def test_competitor_window_only_counts_recent_paid_direct_deals():
    brands = pd.DataFrame({"brand": ["Gritzo"], "category": ["direct_kids_nutrition"]})
    d = c.competitor_deals(toy_posts(), brands)
    paid = d[d.is_sponsored == "yes"]
    assert paid.days_ago.tolist() == [26]       # the organic 2026-05-01 Gritzo mention is not a deal


def test_real_data_rules():
    f = c.creator_features(*c.load())
    sub = c.subscores(f).join(f[["handle"]])
    excl = set(f.loc[c.excluded(f, "hard_exclude"), "handle"])
    assert len(c.excluded(f, "penalty")) == 0
    assert excl == {"sia_3vedi", "ekamichildcare", "couple_adishiv", "doc_mama_and_babies",
                    "raja_choudhary04", "instamommy_suchi"}
    assert ((sub.drop(columns="handle") >= 0) & (sub.drop(columns="handle") <= 1)).all().all()
    # Audience data must not move the score: it only exists for 3 creators.
    assert "audience_bonus_info" not in sub.columns
