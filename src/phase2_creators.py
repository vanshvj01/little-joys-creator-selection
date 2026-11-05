"""Phase 2: creator features and fit scoring.

Three pillars, each scored 0-1 from creators.csv + creator_posts.csv:
  fit    can the creator naturally deliver the Phase 1 winning ingredients?
  reach  how many people see them, and do those people engage?
  safety the inverse of risk: competitor deals, sponsored fatigue, sponsored posts that tank.

Every weight is a named constant below. Audience data (3 of 20 creators) is shown but NOT scored.
Brand categories are a hand annotation (annotations/brand_categories.csv) because the data does not
say what each brand sells.

Run:  python src/phase2_creators.py
"""
import numpy as np
import pandas as pd

import metrics as m

AS_OF = pd.Timestamp("2026-10-27")          # latest post date in the file
RECENT_COMPETITOR_DAYS = 120
N_SENSITIVITY = 5000                         # random weight draws per sensitivity run
# "hard_exclude": a paid deal with a direct kids-nutrition competitor in the last RECENT_COMPETITOR_DAYS
# removes the creator. "penalty": it only lowers the safety pillar. (Decision pending at Phase 2 checkpoint.)
COMPETITOR_RULE = "hard_exclude"
HIDDEN_LIKES_MAX = 5                         # likes <= this on a video with plays = hidden like count
MIN_SPONSORED_FOR_COMPARISON = 3

# --- weights (editable) ---------------------------------------------------------------------------
PILLAR_WEIGHTS = {"fit": 0.50, "reach": 0.25, "safety": 0.25}
FIT_WEIGHTS = {
    "kids_3_12_on_camera": 0.30,     # Phase 1 #1: a child tasting on camera needs a child of product age
    "child_food_moments": 0.20,      # ...and the creator already films kids eating / food moments
    "child_presenter": 0.15,         # Phase 1 #2: child-led ads
    "english_or_hinglish": 0.25,     # Phase 1 #3: English/Hinglish beat regional languages
    "not_authority_style": 0.10,     # Phase 1 avoid: science / authority persuasion
}
REACH_WEIGHTS = {"median_plays": 0.50, "engagement": 0.30, "consistency": 0.20}
SAFETY_WEIGHTS = {"no_competitor_deal": 0.60, "low_sponsored_share": 0.20, "sponsored_holds_up": 0.20}

# Spoken-language credit (transcript_language). Hindi was inconclusive in Phase 1 (x1.31, CI 0.89-1.63),
# so half credit. Telugu / Gujarati / others were never tested in an ad: no credit, flagged as untested.
LANGUAGE_CREDIT = {"english": 1.0, "hinglish": 1.0, "hindi": 0.5}

FOOD_PATTERN = (r"\beat|eating|\bate\b|food|snack|meal|breakfast|lunch|dinner|tiffin|recipe|milk|doodh|"
                r"taste|tasty|yumm|cook|kitchen|khana|nashta|fruit|veggie|vegetable|picky|fussy|nutrition")


def load():
    creators = pd.read_csv(m.DATA / "creators.csv")
    posts = pd.read_csv(m.DATA / "creator_posts.csv", parse_dates=["posted_on"])
    audience = pd.read_csv(m.DATA / "creator_audience.csv")
    brands = pd.read_csv(m.ROOT / "annotations" / "brand_categories.csv")
    return creators, posts, audience, brands


def post_features(posts: pd.DataFrame) -> pd.DataFrame:
    p = posts.copy()
    p["is_video"] = p.plays.fillna(0) > 0
    p["likes_hidden"] = p.is_video & (p.likes <= HIDDEN_LIKES_MAX)
    p["like_rate"] = np.where(p.is_video & ~p.likes_hidden, p.likes / p.plays, np.nan)
    p["talk_rate"] = np.where(p.is_video, (p.comments + p.reshares) / p.plays, np.nan)
    text = (p.topic.fillna("") + " | " + p.what_stands_out.fillna("") + " | " + p.caption.fillna("")
            + " | " + p.transcript.fillna("")).str.lower()
    p["kid_3_12"] = p.children_on_camera.eq("yes") & p.child_ages.fillna("").str.contains("3-7|8-12")
    p["child_food"] = p.kid_3_12 & text.str.contains(FOOD_PATTERN, regex=True)
    p["child_presenter"] = p.presenter_age.isin(["3-7", "8-12"])
    p["authority_style"] = p.content_type.eq("expert_explainer")
    p["sponsored"] = p.is_sponsored.eq("yes")
    lang = p.transcript_language.str.lower().str.extract(r"^(\w+)")[0]
    p["spoken_lang"] = lang
    p["lang_credit"] = lang.map(LANGUAGE_CREDIT).fillna(0.0).where(lang.notna())
    return p


def competitor_deals(posts: pd.DataFrame, brands: pd.DataFrame) -> pd.DataFrame:
    cat = dict(zip(brands.brand.str.lower(), brands.category))
    b = posts[["creator_id", "post_url", "posted_on", "is_sponsored", "brands_visible"]].dropna(subset=["brands_visible"])
    b = b.assign(brand=b.brands_visible.str.split("; ")).explode("brand")
    b["category"] = b.brand.str.strip().str.lower().map(cat).fillna("other")
    b["days_ago"] = (AS_OF - b.posted_on).dt.days
    return b[b.category != "other"]


def creator_features(creators, posts, audience, brands) -> pd.DataFrame:
    p = post_features(posts)
    g = p.groupby("creator_id")
    v = p[p.is_video].groupby("creator_id")
    f = pd.DataFrame({
        "posts": g.size(),
        "video_posts": v.size(),
        "median_plays": v.plays.median(),
        "plays_iqr_log10": v.plays.apply(lambda s: np.subtract(*np.percentile(np.log10(s), [75, 25]))),
        "median_like_rate": v.like_rate.median(),
        "hidden_like_posts": g.likes_hidden.sum(),
        "median_talk_rate": v.talk_rate.median(),
        "kids_3_12_on_camera": g.kid_3_12.mean(),
        "child_food_moments": g.child_food.mean(),
        "child_presenter": g.child_presenter.mean(),
        "authority_share": g.authority_style.mean(),
        "transcripts": g.spoken_lang.count(),
        "english_or_hinglish": g.lang_credit.mean(),
        "spoken_languages": g.spoken_lang.apply(lambda s: ", ".join(f"{k} {n}" for k, n in s.value_counts().items())),
        "sponsored_posts": g.sponsored.sum(),
        "sponsored_share": g.sponsored.mean(),
        "production_quality_median": g.production_quality_1to5.median(),
        "last_post": g.posted_on.max(),
        "posts_last_60d": g.posted_on.apply(lambda s: int((s >= AS_OF - pd.Timedelta(days=60)).sum())),
    })
    # Does sponsored content tank? Median plays of sponsored vs organic videos (same creator).
    def spon_ratio(df):
        s, o = df[df.sponsored], df[~df.sponsored]
        if len(s) < MIN_SPONSORED_FOR_COMPARISON or len(o) < MIN_SPONSORED_FOR_COMPARISON:
            return np.nan
        return s.plays.median() / o.plays.median()
    f["sponsored_vs_organic_plays"] = p[p.is_video].groupby("creator_id").apply(spon_ratio)

    deals = competitor_deals(posts, brands)
    direct = deals[(deals.category == "direct_kids_nutrition") & deals.is_sponsored.eq("yes")]
    f["direct_competitor_deals"] = direct.groupby("creator_id").apply(
        lambda d: "; ".join(f"{r.brand} ({r.posted_on:%Y-%m-%d})" for r in d.itertuples()))
    f["days_since_competitor_deal"] = direct.groupby("creator_id").days_ago.min()
    f["adjacent_brands"] = deals[deals.category.str.startswith("adjacent")].groupby("creator_id").brand.apply(
        lambda s: ", ".join(sorted(set(s))))
    f["prior_little_joys_post"] = deals[deals.category == "own_brand"].groupby("creator_id").posted_on.max()

    out = creators.set_index("creator_id")[["handle", "name", "followers", "verified", "persona"]].join(f)
    aud = audience.set_index("creator_id")
    out["audience_bonus_info"] = aud.apply(
        lambda r: f"{r.platform}: women {r.women_pct:.0f}%, {r.age_split}; top countries {r.top_countries}; "
                  f"past brands: {r.brands_in_past_year if isinstance(r.brands_in_past_year, str) else 'none listed'}",
        axis=1)
    return out


def minmax(s: pd.Series) -> pd.Series:
    rng = s.max() - s.min()
    return (s - s.min()) / rng if rng > 0 else s * 0 + 0.5


def subscores(f: pd.DataFrame) -> pd.DataFrame:
    s = pd.DataFrame(index=f.index)
    # fit (raw shares already 0-1; food moments are rare so scaled to the best creator)
    s["kids_3_12_on_camera"] = f.kids_3_12_on_camera
    s["child_food_moments"] = minmax(f.child_food_moments)
    s["child_presenter"] = f.child_presenter
    s["english_or_hinglish"] = f.english_or_hinglish.fillna(0.5)
    s["not_authority_style"] = 1 - f.authority_share
    # reach
    s["median_plays"] = minmax(np.log10(f.median_plays))
    like = minmax(np.log10(f.median_like_rate))
    talk = minmax(np.log10(f.median_talk_rate))
    s["engagement"] = pd.concat([like, talk], axis=1).mean(axis=1)   # hidden likes: like part from visible posts only
    s["consistency"] = 1 - minmax(f.plays_iqr_log10)
    # safety
    d = f.days_since_competitor_deal
    s["no_competitor_deal"] = np.where(d.isna(), 1.0, np.where(d <= RECENT_COMPETITOR_DAYS, 0.0, 0.5))
    s["low_sponsored_share"] = 1 - f.sponsored_share
    s["sponsored_holds_up"] = f.sponsored_vs_organic_plays.clip(upper=1).fillna(0.75)  # unknown = mild discount
    return s


def score(sub: pd.DataFrame, pillar_w=PILLAR_WEIGHTS, fit_w=FIT_WEIGHTS, reach_w=REACH_WEIGHTS,
          safety_w=SAFETY_WEIGHTS) -> pd.DataFrame:
    def combine(w):
        tot = sum(w.values())
        return sum(sub[k] * v for k, v in w.items()) / tot
    out = pd.DataFrame({"fit": combine(fit_w), "reach": combine(reach_w), "safety": combine(safety_w)})
    tot = sum(pillar_w.values())
    out["total"] = sum(out[k] * v for k, v in pillar_w.items()) / tot
    out["rank"] = out.total.rank(ascending=False, method="min").astype(int)
    return out


def dirichlet_around(base: dict, rng, concentration: float) -> dict:
    keys = list(base)
    w = rng.dirichlet(np.array([base[k] for k in keys]) * concentration)
    return dict(zip(keys, w))


def excluded(f: pd.DataFrame, rule: str = None) -> pd.Index:
    rule = rule or COMPETITOR_RULE
    if rule == "penalty":
        return f.index[:0]
    return f.index[f.days_since_competitor_deal <= RECENT_COMPETITOR_DAYS]


def sensitivity(sub: pd.DataFrame, n: int = N_SENSITIVITY, seed: int = 11, exclude=()) -> pd.DataFrame:
    """How often is each creator in the top 5 when weights are perturbed?

    local:  all four weight sets drawn around the base weights (Dirichlet, concentration 20 — typical
            pillar weight moves of about ±0.1).
    wide:   pillar weights drawn uniformly over all possible splits; sub-weights stay at base.
    """
    rng = np.random.default_rng(seed)
    res = {}
    for name, conc in [("local", 20.0), ("wide", None)]:
        hits = pd.Series(0, index=sub.index)
        for _ in range(n):
            if conc is None:
                pw = dirichlet_around({k: 1 for k in PILLAR_WEIGHTS}, rng, 1.0)
                sc = score(sub, pw)
            else:
                sc = score(sub, dirichlet_around(PILLAR_WEIGHTS, rng, conc), dirichlet_around(FIT_WEIGHTS, rng, conc),
                           dirichlet_around(REACH_WEIGHTS, rng, conc), dirichlet_around(SAFETY_WEIGHTS, rng, conc))
            sc.loc[list(exclude), "total"] = -1
            hits[sc.nlargest(5, "total").index] += 1
        res[f"top5_share_{name}"] = hits / n
    return pd.DataFrame(res)


SCENARIOS = {
    "base": dict(),
    "equal_pillars": dict(pillar_w={"fit": 1, "reach": 1, "safety": 1}),
    "fit_heavy": dict(pillar_w={"fit": 0.7, "reach": 0.15, "safety": 0.15}),
    "reach_heavy": dict(pillar_w={"fit": 0.3, "reach": 0.5, "safety": 0.2}),
    "safety_heavy": dict(pillar_w={"fit": 0.3, "reach": 0.2, "safety": 0.5}),
    "language_ignored": dict(fit_w={**FIT_WEIGHTS, "english_or_hinglish": 0.0}),
    "language_strict": dict(fit_w={**FIT_WEIGHTS, "english_or_hinglish": 0.60}),
    "no_child_presenter": dict(fit_w={**FIT_WEIGHTS, "child_presenter": 0.0}),
}


def scenarios(sub: pd.DataFrame, exclude=()) -> pd.DataFrame:
    out = {}
    for name, kw in SCENARIOS.items():
        sc = score(sub, **kw)
        sc.loc[list(exclude), "total"] = -1
        out[name] = sc.total.rank(ascending=False, method="min").astype(int)
    return pd.DataFrame(out)


def run():
    creators, posts, audience, brands = load()
    f = creator_features(creators, posts, audience, brands)
    sub = subscores(f)
    sc = score(sub)
    excl = excluded(f)
    sc["excluded_competitor_deal"] = sc.index.isin(excl)
    sc["rank"] = sc.total.where(~sc.excluded_competitor_deal, -1).rank(ascending=False, method="min").astype(int)
    sens = sensitivity(sub, exclude=excl)
    sens_pen = sensitivity(sub, exclude=()).add_suffix("_if_penalty_only")
    scen = scenarios(sub, exclude=excl)
    table = (f[["handle"]].join(sc).join(sens).join(sens_pen).join(scen.add_prefix("rank_"))
             .sort_values("rank"))
    table["in_top5_scenarios"] = (scen.reindex(table.index) <= 5).sum(axis=1).astype(str) + f"/{len(scen.columns)}"
    table["rank_if_penalty_only"] = score(sub)["rank"]
    m.OUT.mkdir(exist_ok=True)
    f.to_csv(m.OUT / "phase2_creator_features.csv")
    sub.join(f[["handle"]]).to_csv(m.OUT / "phase2_subscores.csv")
    table.to_csv(m.OUT / "phase2_ranking.csv")
    write_reasons(f, table)
    return f, sub, table


def reason(r) -> str:
    """One line on the deciding factors, filled from the feature table (no hand-typed numbers)."""
    bits = []
    if r.excluded_competitor_deal:
        return f"Excluded: paid direct-competitor post(s) {r.direct_competitor_deals}."
    if r.kids_3_12_on_camera == 0:
        bits.append("no child aged 3-12 appears in any recent post")
    elif r.kids_3_12_on_camera < 0.2:
        bits.append(f"a child aged 3-12 appears in only {r.kids_3_12_on_camera:.0%} of posts")
    if r.authority_share >= 0.5:
        bits.append(f"{r.authority_share:.0%} of posts are doctor-style explainers (science/authority ads did not do better)")
    if r.english_or_hinglish < 0.5:
        bits.append(f"speaks mostly {r.spoken_languages.split(' ')[0].title()} on camera (untested in ads)")
    if r.median_plays < 100_000:
        bits.append(f"small reach (median {r.median_plays/1000:.0f}k plays)")
    if r.sponsored_share >= 0.75:
        bits.append(f"{r.sponsored_share:.0%} of recent posts are sponsored")
    if isinstance(r.sponsored_vs_organic_plays, float) and r.sponsored_vs_organic_plays < 0.6:
        bits.append(f"sponsored posts get {r.sponsored_vs_organic_plays:.0%} of organic plays")
    if r.child_food_moments == 0 and r.kids_3_12_on_camera >= 0.2:
        bits.append("never films children around food")
    return "; ".join(bits) if bits else "no single weakness; outscored on the combined total"


def write_reasons(f: pd.DataFrame, table: pd.DataFrame) -> pd.DataFrame:
    t = table[["handle", "rank", "total", "fit", "reach", "safety", "excluded_competitor_deal",
               "top5_share_local", "top5_share_wide"]].join(f.drop(columns=["handle"]))
    t["one_line_reason"] = t.apply(reason, axis=1)
    t["robustness"] = np.select(
        [t.excluded_competitor_deal, t.top5_share_local >= 0.8, t.top5_share_local >= 0.4],
        ["excluded", "robust", "marginal"], "out")
    out = t[["handle", "rank", "robustness", "total", "fit", "reach", "safety", "top5_share_local",
             "top5_share_wide", "one_line_reason"]]
    out.to_csv(m.OUT / "phase2_reasons.csv")
    return out


if __name__ == "__main__":
    pd.set_option("display.width", 260)
    f, sub, table = run()
    cols = ["handle", "fit", "reach", "safety", "total", "rank", "excluded_competitor_deal", "top5_share_local",
            "top5_share_wide", "in_top5_scenarios", "rank_if_penalty_only", "top5_share_local_if_penalty_only"]
    print(table[cols].round(2).to_string())
    print()
    print(table[[c for c in table.columns if c.startswith("rank_")]].assign(handle=table.handle).set_index("handle").to_string())
