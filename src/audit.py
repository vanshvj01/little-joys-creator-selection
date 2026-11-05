"""Phase 0 data audit: schema, row counts, nulls, label distributions, anomalies.

Run:  python -P src/audit.py  > outputs/audit.txt
Every number printed here is computed directly from data/*.csv.
"""
from pathlib import Path

import pandas as pd

DATA = Path(__file__).resolve().parent.parent / "data"
LIST_SEP = "; "
END_DATE = pd.Timestamp("2026-10-26")

# Free-text columns: don't print value distributions for these.
FREE_TEXT = {
    "ads": {"video_url", "ad_copy", "transcript", "hook_line", "on_screen_text",
            "meta_ad_library_id", "ad_id", "launch_date", "stopped_date", "claims_made"},
    "creator_posts": {"post_url", "caption", "transcript", "on_screen_text",
                      "what_stands_out", "posted_on", "handle", "creator_id"},
}
PERF = ["spend_inr", "impressions", "video_3s_views", "thruplays",
        "link_clicks", "add_to_carts", "purchases", "revenue_inr"]


def load(name):
    return pd.read_csv(DATA / f"{name}.csv")


def section(title):
    print(f"\n{'=' * 78}\n{title}\n{'=' * 78}")


def schema(df, name):
    section(f"{name}: {df.shape[0]} rows x {df.shape[1]} cols")
    out = pd.DataFrame({
        "dtype": df.dtypes.astype(str),
        "nulls": df.isna().sum(),
        "blank_str": df.apply(lambda s: (s.astype(str).str.strip() == "").sum() if s.dtype == object else 0),
        "n_unique": df.nunique(),
    })
    print(out.to_string())


def is_list_col(s):
    return s.dropna().astype(str).str.contains(LIST_SEP, regex=False).mean() > 0.05


def distributions(df, name, max_levels=25):
    section(f"{name}: categorical label distributions")
    for col in df.columns:
        if col in FREE_TEXT.get(name, set()) or pd.api.types.is_numeric_dtype(df[col]):
            continue
        s = df[col]
        if is_list_col(s):
            vals = s.dropna().astype(str).str.split(LIST_SEP).explode().str.strip()
            tag = " [multi-value, exploded]"
        else:
            vals, tag = s, ""
        vc = vals.value_counts(dropna=False)
        if len(vc) > max_levels:
            print(f"\n-- {col}{tag}: {len(vc)} levels (top {max_levels} shown)")
            vc = vc.head(max_levels)
        else:
            print(f"\n-- {col}{tag}")
        print(vc.to_string())


def numeric_summary(df, name):
    section(f"{name}: numeric summary")
    print(df.select_dtypes("number").describe().T.round(2).to_string())


def ads_anomalies(ads):
    section("ads: anomalies / integrity checks")
    checks = {
        "duplicate ad_id": ads.ad_id.duplicated().sum(),
        "duplicate meta_ad_library_id": ads.meta_ad_library_id.duplicated().sum(),
        "duplicate video_url": ads.video_url.duplicated().sum(),
        "duplicate transcript (non-null)": ads.transcript.dropna().duplicated().sum(),
        "zero spend": (ads.spend_inr == 0).sum(),
        "zero impressions": (ads.impressions == 0).sum(),
        "zero purchases": (ads.purchases == 0).sum(),
        "3s views > impressions": (ads.video_3s_views > ads.impressions).sum(),
        "thruplays > 3s views": (ads.thruplays > ads.video_3s_views).sum(),
        "clicks > impressions": (ads.link_clicks > ads.impressions).sum(),
        "ATC > clicks": (ads.add_to_carts > ads.link_clicks).sum(),
        "purchases > ATC": (ads.purchases > ads.add_to_carts).sum(),
        "purchases > clicks": (ads.purchases > ads.link_clicks).sum(),
        "revenue>0 but purchases==0": ((ads.revenue_inr > 0) & (ads.purchases == 0)).sum(),
        "purchases>0 but revenue==0": ((ads.revenue_inr == 0) & (ads.purchases > 0)).sum(),
        "negative perf values": (ads[PERF] < 0).any(axis=1).sum(),
    }
    for k, v in checks.items():
        print(f"{k:40s} {v}")

    launch = pd.to_datetime(ads.launch_date, errors="coerce")
    stop = pd.to_datetime(ads.stopped_date, errors="coerce")
    print(f"\nlaunch_date range: {launch.min().date()} -> {launch.max().date()}  (unparseable: {launch.isna().sum() - ads.launch_date.isna().sum()})")
    print(f"stopped_date range: {stop.min().date()} -> {stop.max().date()}")
    print(f"still live (blank stopped_date): {stop.isna().sum()}")
    print(f"stopped before launch: {(stop < launch).sum()}")
    print(f"stopped after cap {END_DATE.date()}: {(stop > END_DATE).sum()}")

    expected = (stop.fillna(END_DATE).clip(upper=END_DATE) - launch).dt.days
    diff = ads.days_live - expected
    print(f"days_live vs (min(stop, cap) - launch): exact={int((diff == 0).sum())}, "
          f"off_by_1={int((diff.abs() == 1).sum())}, other={int((diff.abs() > 1).sum())}")
    if (diff.abs() > 1).any():
        print(ads.loc[diff.abs() > 1, ["ad_id", "launch_date", "stopped_date", "days_live"]].assign(expected=expected).to_string())

    # Derived-rate sanity (account level)
    t = ads[PERF].sum()
    print("\nAccount totals:")
    print(t.to_string())
    print(f"account ROAS = {t.revenue_inr / t.spend_inr:.2f}, CPA = ₹{t.spend_inr / t.purchases:.0f}, "
          f"AOV = ₹{t.revenue_inr / t.purchases:.0f}, CTR = {t.link_clicks / t.impressions:.2%}")

    per_ad = ads.assign(
        roas=ads.revenue_inr / ads.spend_inr,
        aov=ads.revenue_inr / ads.purchases.where(ads.purchases > 0),
        ctr=ads.link_clicks / ads.impressions,
        cpm=ads.spend_inr / ads.impressions * 1000,
    )
    print("\nPer-ad derived metric spread:")
    print(per_ad[["roas", "aov", "ctr", "cpm"]].describe().round(3).to_string())

    spend_share = ads.spend_inr.sort_values(ascending=False).cumsum() / ads.spend_inr.sum()
    print(f"\nspend concentration: top 10 ads = {spend_share.iloc[9]:.0%} of spend, top 20 = {spend_share.iloc[19]:.0%}")
    print(f"ads with < 20 purchases: {(ads.purchases < 20).sum()}  (< 5: {(ads.purchases < 5).sum()})")
    print(f"ads with blank transcript: {ads.transcript.isna().sum()}, blank hook_line: {ads.hook_line.isna().sum()}")

    # Correlation of spend with days_live and duration (confounder preview)
    print("\nSpearman corr (spend vs days_live, duration_s, roas):")
    print(per_ad[["spend_inr", "days_live", "duration_s", "roas"]].corr(method="spearman").round(2).to_string())


def creator_anomalies(creators, posts, aud):
    section("creators / posts / audience: anomalies")
    print(f"duplicate creator_id: {creators.creator_id.duplicated().sum()}, duplicate handle: {creators.handle.duplicated().sum()}")
    print(f"duplicate post_url: {posts.post_url.duplicated().sum()}")
    print(f"post creator_ids not in creators.csv: {set(posts.creator_id) - set(creators.creator_id)}")
    print(f"audience creator_ids not in creators.csv: {set(aud.creator_id) - set(creators.creator_id)}")
    n = posts.groupby("creator_id").size().rename("posts_actual")
    chk = creators.set_index("creator_id")[["handle", "followers", "posts_in_file"]].join(n)
    chk["mismatch"] = chk.posts_in_file != chk.posts_actual
    print("\nposts_in_file vs actual rows:")
    print(chk.to_string())

    posted = pd.to_datetime(posts.posted_on, errors="coerce")
    print(f"\nposted_on range: {posted.min()} -> {posted.max()} (unparseable: {posted.isna().sum()})")

    print("\nLikes hidden / tiny (likes <= 5), by creator:")
    hid = posts.assign(hidden=posts.likes.fillna(0) <= 5).groupby("handle").agg(
        posts=("post_url", "size"), hidden_like_posts=("hidden", "sum"),
        median_likes=("likes", "median"), median_plays=("plays", "median"),
        median_comments=("comments", "median"))
    print(hid.sort_values("hidden_like_posts", ascending=False).to_string())

    print(f"\nposts with plays null/0: {(posts.plays.fillna(0) == 0).sum()}  "
          f"(by type: {posts.loc[posts.plays.fillna(0) == 0, 'type'].value_counts().to_dict()})")
    print(f"posts with likes > plays (where plays>0): {((posts.likes > posts.plays) & (posts.plays > 0)).sum()}")
    print(f"posts with transcript: {posts.transcript.notna().sum()}")
    print(f"sponsored posts: {posts.is_sponsored.value_counts(dropna=False).to_dict()}")
    print("\nAudience file:")
    print(aud.to_string())


def main():
    pd.set_option("display.width", 200)
    ads, creators = load("ads"), load("creators")
    posts, aud = load("creator_posts"), load("creator_audience")

    for df, name in [(ads, "ads"), (creators, "creators"), (posts, "creator_posts"), (aud, "creator_audience")]:
        schema(df, name)
    numeric_summary(ads, "ads")
    distributions(ads, "ads")
    ads_anomalies(ads)
    numeric_summary(posts, "creator_posts")
    distributions(posts, "creator_posts")
    creator_anomalies(creators, posts, aud)


if __name__ == "__main__":
    main()
