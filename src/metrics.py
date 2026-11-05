"""Single source of truth for ad metric definitions and the bootstrap used everywhere.

All group-level ratios are pooled (sum of numerator / sum of denominator), which is the same as
weighting each ad's ratio by its denominator. For CPA that means spend-weighted.
"""
import difflib
import itertools
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
OUT = ROOT / "outputs"
LIST_SEP = "; "
END_DATE = pd.Timestamp("2026-10-26")

# Decisions from the Phase 0 checkpoint (docs/prompts.md).
EXCLUDED_ADS = {"LJ-089": "₹4.3L spend, 1,544 add-to-carts, 0 purchases: probable tracking break"}
# Transcripts at least this similar are the same script re-edited (e.g. LJ-006 / LJ-097).
SCRIPT_SIMILARITY = 0.80
# Stop batches with < MIN_BATCH ads are merged into the nearest larger batch by date.
MIN_BATCH = 5

# (numerator, denominator) for every pooled funnel metric.
RATIOS = {
    "ctr": ("link_clicks", "impressions"),         # click-through rate
    "hook_rate": ("video_3s_views", "impressions"),  # share of impressions watched 3s
    "hold_rate": ("thruplays", "video_3s_views"),    # of 3s viewers, share who reach ThruPlay
    "atc_rate": ("add_to_carts", "link_clicks"),    # add-to-cart per click
    "cvr": ("purchases", "link_clicks"),            # purchase per click
    "cpa": ("spend_inr", "purchases"),              # ₹ per purchase  (PRIMARY, lower = better)
    "roas": ("revenue_inr", "spend_inr"),           # revenue per ₹ spent
    "cpm": ("spend_inr", "impressions"),            # ×1000 applied below
}


def safe_div(num, den):
    num = np.asarray(num, dtype=float)
    den = np.asarray(den, dtype=float)
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(den > 0, num / den, np.nan)


def add_ad_metrics(ads: pd.DataFrame) -> pd.DataFrame:
    """Per-ad funnel metrics. CPA is NaN for ads with 0 purchases (not infinite)."""
    out = ads.copy()
    for name, (num, den) in RATIOS.items():
        out[name] = safe_div(out[num], out[den])
    out["cpm"] = out["cpm"] * 1000
    out["aov"] = safe_div(out.revenue_inr, out.purchases)
    return out


def pooled(df: pd.DataFrame) -> dict:
    """Pooled (spend-weighted) metrics for a group of ads."""
    s = df[["spend_inr", "impressions", "video_3s_views", "thruplays", "link_clicks",
            "add_to_carts", "purchases", "revenue_inr"]].sum()
    res = {name: float(safe_div(s[num], s[den])) for name, (num, den) in RATIOS.items()}
    res["cpm"] *= 1000
    res.update(n_ads=len(df), spend_inr=float(s.spend_inr), purchases=float(s.purchases))
    return res


def load_ads(include_excluded: bool = False) -> pd.DataFrame:
    ads = pd.read_csv(DATA / "ads.csv")
    ads = add_ad_metrics(ads)
    ads["cluster"] = video_clusters(ads)
    ads["stop_batch"] = stop_batches(ads.stopped_date)
    if not include_excluded:
        ads = ads[~ads.ad_id.isin(EXCLUDED_ADS)].reset_index(drop=True)
    return ads


def video_clusters(ads: pd.DataFrame) -> pd.Series:
    """Ads that share a video_url, or whose transcripts are near-identical, are one creative.

    Returns a cluster id per ad (the smallest ad_id in the cluster).
    """
    ids = ads.ad_id.tolist()
    parent = {i: i for i in ids}

    def find(x):
        while parent[x] != x:
            x = parent[x]
        return x

    def union(x, y):
        rx, ry = sorted([find(x), find(y)])
        parent[ry] = rx

    for _, g in ads.groupby("video_url"):
        for x in g.ad_id.iloc[1:]:
            union(g.ad_id.iloc[0], x)
    text = (ads.transcript.fillna("").str.lower().str.replace(r"[^\w\s]", "", regex=True)
            .str.split().str.join(" ").tolist())
    for i, j in itertools.combinations(range(len(ads)), 2):
        if len(text[i]) < 80 or len(text[j]) < 80:   # silent / music-only ads have stub transcripts
            continue
        sm = difflib.SequenceMatcher(None, text[i], text[j], autojunk=False)
        if sm.quick_ratio() >= SCRIPT_SIMILARITY and sm.ratio() >= SCRIPT_SIMILARITY:
            union(ids[i], ids[j])
    return pd.Series([find(i) for i in ids], index=ads.index)


def stop_batches(stopped: pd.Series) -> pd.Series:
    """Stop date as a batch label, with tiny batches merged into the nearest batch with >= MIN_BATCH ads."""
    d = pd.to_datetime(stopped)
    counts = d.value_counts()
    big = counts[counts >= MIN_BATCH].index
    def nearest(x):
        if x in big:
            return x
        return min(big, key=lambda b: abs((b - x).days))
    return d.map(nearest).dt.strftime("%Y-%m-%d")


def cluster_bootstrap_weights(clusters: pd.Series, n_boot: int, seed: int = 0) -> np.ndarray:
    """(n_boot × n_ads) matrix of how many times each ad is drawn when resampling clusters.

    Resampling whole clusters means a video that ran as two ads is never treated as two
    independent pieces of evidence.
    """
    rng = np.random.default_rng(seed)
    codes, uniq = pd.factorize(clusters)
    k = len(uniq)
    draws = rng.integers(0, k, size=(n_boot, k))
    cluster_counts = np.zeros((n_boot, k))
    np.add.at(cluster_counts, (np.arange(n_boot)[:, None], draws), 1)
    return cluster_counts[:, codes]


def explode_labels(s: pd.Series) -> pd.Series:
    """Split a '; '-separated label cell into a list of stripped values (NaN -> [])."""
    return s.fillna("").astype(str).apply(lambda x: [v.strip() for v in x.split(LIST_SEP) if v.strip()])
