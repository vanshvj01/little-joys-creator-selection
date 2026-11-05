import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
import metrics as m  # noqa: E402


def toy():
    return pd.DataFrame({
        "ad_id": ["A", "B", "C"],
        "transcript": ["", "", ""],
        "video_url": ["u1", "u2", "u1"],
        "stopped_date": ["2026-10-01"] * 3,
        "spend_inr": [1000, 3000, 0],
        "impressions": [10000, 20000, 0],
        "video_3s_views": [4000, 5000, 0],
        "thruplays": [1000, 1000, 0],
        "link_clicks": [100, 300, 0],
        "add_to_carts": [20, 30, 0],
        "purchases": [10, 0, 0],
        "revenue_inr": [6000, 0, 0],
    })


def test_ad_metrics_definitions():
    a = m.add_ad_metrics(toy())
    assert a.loc[0, "cpa"] == 100
    assert a.loc[0, "roas"] == 6
    assert a.loc[0, "ctr"] == pytest.approx(0.01)
    assert a.loc[0, "hook_rate"] == pytest.approx(0.4)
    assert a.loc[0, "hold_rate"] == pytest.approx(0.25)
    assert a.loc[0, "atc_rate"] == pytest.approx(0.2)
    assert a.loc[0, "cvr"] == pytest.approx(0.1)
    assert a.loc[0, "cpm"] == pytest.approx(100)


def test_zero_denominators_are_nan_not_inf():
    a = m.add_ad_metrics(toy())
    assert np.isnan(a.loc[1, "cpa"])  # 0 purchases
    assert np.isnan(a.loc[2, "ctr"])  # 0 impressions
    assert not np.isinf(a[["cpa", "ctr", "roas"]].to_numpy(dtype=float)).any()


def test_pooled_is_spend_weighted_not_mean_of_ratios():
    p = m.pooled(toy())
    # pooled CPA = 4000 / 10, not mean(100, nan)
    assert p["cpa"] == 400
    assert p["roas"] == pytest.approx(6000 / 4000)


def test_cluster_bootstrap_keeps_duplicate_videos_together():
    w = m.cluster_bootstrap_weights(pd.Series(["u1", "u2", "u1"]), n_boot=500, seed=1)
    assert w.shape == (500, 3)
    assert (w[:, 0] == w[:, 2]).all()          # same video => always drawn together
    # 2 clusters drawn per replicate: cluster u1 contributes 2 ads per draw, u2 one.
    assert ((w[:, 0] + w[:, 1]) == 2).all()


def test_stop_batches_merge_small():
    s = pd.Series(["2026-10-01"] * 5 + ["2026-10-03"] + ["2026-12-01"] * 5)
    b = m.stop_batches(s)
    assert b.iloc[5] == "2026-10-01"
    assert b.nunique() == 2


def test_real_data_integrity():
    ads = m.load_ads(include_excluded=True)
    assert len(ads) == 100
    assert (ads.purchases <= ads.add_to_carts).all()
    assert (ads.add_to_carts <= ads.link_clicks).all()
    assert (ads.thruplays <= ads.video_3s_views).all()
    assert (ads.video_3s_views <= ads.impressions).all()
    assert len(m.load_ads()) == 99
    # 3 shared-video pairs + 3 near-identical scripts (LJ-006/097, LJ-018/079, LJ-033/092)
    assert ads.cluster.nunique() == 94
    assert ads.set_index("ad_id").cluster["LJ-097"] == "LJ-006"
