"""Phase 1: which ad ingredients go with cheaper purchases?

For every label level we compare ads WITH it vs ads WITHOUT it on pooled (spend-weighted) CPA:

    cpa_ratio = CPA(with) / CPA(without)        < 1 means the ingredient goes with cheaper purchases

Two versions:
  raw       straight pooled comparison.
  adjusted  each ad's purchases are compared to what a baseline model expects for its stop batch and
            product (Poisson model, log-spend offset). This removes the two big confounders found in the
            audit: some stop batches converted ~2x better than others, and milk-mix ads convert far
            better than gummies / other products.

Uncertainty: cluster bootstrap over creatives (duplicate videos resampled together), N_BOOT draws.
Verdicts are rule-based (see `verdict`) and the thresholds are constants below.

Run:  python -P src/phase1_ads.py
"""
import re

import numpy as np
import pandas as pd

import metrics as m

N_BOOT = 2000
SEED = 7
MIN_N = 8            # fewer ads than this on either side: not tested
STRONG_MIN_N = 10
FDR_Q = 0.10         # Benjamini–Hochberg threshold for "strong"
SUGGESTIVE_CI = 0.90

SINGLE = ["hook_type", "hook_driver", "hook_delivered_by", "ad_format", "story_structure",
          "main_benefit", "performance_style", "creator_type", "creator_gender", "creator_age",
          "people_on_screen", "child_on_screen", "child_age", "child_in_first_3s", "brand_first_said",
          "brand_said_aloud", "product_form", "product_shown_as", "production", "audio", "music",
          "captions", "language", "language_mixing", "first_frame", "setting", "cta_type", "offer"]
MULTI = ["child_role", "demo_shown", "proof_used", "persuasion", "narratives", "ad_categories"]
CONFOUNDERS = ["stop_batch", "product_form"]

# Features derived from the transcript / hook_line text itself (not from AI labels).
TEXT_FEATURES = {
    "hook_line_is_question": ("hook_line", r"\?"),
    "brand_named_in_hook_line": ("hook_line", r"little\s*joys|nutrimix|nutri\s*mix"),
    "says_grams_of_protein": ("transcript", r"\d+\s*(?:g|gm|gms|gram|grams)\b"),
    "mentions_sugar": ("transcript", r"sugar|cheeni|chini"),
    "mentions_picky_fussy": ("transcript", r"picky|fussy|nakhr|nakhre|refuse"),
    "mentions_taste": ("transcript", r"tast|yumm|delicious|chocolat|\bmast\b|swad"),
    "mentions_doctor": ("transcript", r"doctor|paediatric|pediatric|nutritionist|dietitian"),
    "mentions_milk": ("transcript", r"\bmilk\b|doodh|dudh"),
    "mentions_protein": ("transcript", r"protein"),
    "mentions_immunity": ("transcript", r"immun"),
}
# Added AFTER reading the top/bottom transcripts (hypothesis-generating, so flagged "posthoc" in output).
# claims_made is in English for every ad, so these also work for regional-language ads.
POSTHOC_FEATURES = {
    "claim_taste_unchanged_or_kids_cant_tell": ("claims_made|transcript",
        r"no taste change|taste (?:remains|is) (?:completely )?unchanged|does not change the taste|can'?t tell|"
        r"kuch different nahi|bilkul same|taste toh bilkul"),
    "claim_protein_in_everyday_food_terms": ("claims_made|transcript", r"egg|ande|katori|dal"),
    "claim_ragi_bajra_jaggery_dates_template": ("claims_made", r"(?=.*(?:ragi|bajra))(?=.*jaggery)(?=.*(?:date|23 ))"),
    "claim_deficiency_symptoms": ("claims_made", r"symptom|deficien"),
    "recipe_or_hack_framing": ("transcript|hook_line", r"hack|recipe|pancake|waffle|paratha|roti|shake|smoothie|chilla"),
}


def feature_matrix(ads: pd.DataFrame) -> pd.DataFrame:
    """One boolean column per (label, level). Column names are 'label=level'."""
    cols = {}
    for c in SINGLE:
        vals = ads[c].fillna("(blank)").astype(str)
        for lv in sorted(vals.unique()):
            cols[f"{c}={lv}"] = vals == lv
    for c in MULTI:
        lists = m.explode_labels(ads[c])
        for lv in sorted({v for l in lists for v in l}):
            cols[f"{c}={lv}"] = lists.apply(lambda l, lv=lv: lv in l)
    # Grouped / derived versions of labels that are more useful than their raw levels.
    cols["brand_first_said=within_5s"] = ads.brand_first_said.isin(["under_3s", "3_to_5s"])
    cols["humour=any"] = ads.humour.fillna("none") != "none"
    cols["child_on_screen=any"] = ads.child_on_screen.isin(["one", "multiple"])
    cols["language=English_or_Hinglish"] = ads.language.isin(["English", "Hinglish"])
    cols["language=regional_Indian"] = ads.language.isin(["Kannada", "Malayalam", "Tamil", "Punjabi"])
    for lo, hi in [(0, 25), (25, 40), (40, 60), (60, 999)]:
        cols[f"duration_s={lo}-{hi}"] = (ads.duration_s > lo) & (ads.duration_s <= hi)
    for prefix, table in [("text", TEXT_FEATURES), ("posthoc", POSTHOC_FEATURES)]:
        for name, (src, pat) in table.items():
            text = ads[src.split("|")].fillna("").agg(" ".join, axis=1)
            cols[f"{prefix}:{name}"] = text.str.contains(pat, flags=re.I, regex=True)
    df = pd.DataFrame(cols, index=ads.index).astype(bool)
    # Identical columns (e.g. child_on_screen=none == child_role=none) would be counted as separate
    # evidence; keep the first and record the aliases.
    keep, aliases = [], {}
    for c in df.columns:
        twin = next((k for k in keep if df[k].equals(df[c])), None)
        if twin is None:
            keep.append(c)
        else:
            aliases.setdefault(twin, []).append(c)
    df = df[keep]
    df.attrs["aliases"] = aliases
    return df


def poisson_rates(X: np.ndarray, y: np.ndarray, spend: np.ndarray, w: np.ndarray, iters: int = 30) -> np.ndarray:
    """Expected purchases per ad from `poisson_fit`."""
    return np.exp(X @ poisson_fit(X, y, spend, w, iters) + np.log(spend))


def poisson_fit(X: np.ndarray, y: np.ndarray, spend: np.ndarray, w: np.ndarray, iters: int = 30) -> np.ndarray:
    """Weighted Poisson GLM with log(spend) offset via IRLS; returns coefficients.

    A small ridge term keeps coefficients finite when a bootstrap draw drops a whole category.
    """
    off = np.log(spend)
    beta = np.zeros(X.shape[1])
    beta[0] = np.log(np.sum(w * y) / np.sum(w * spend))
    ridge = 1e-4 * np.eye(X.shape[1])
    ridge[0, 0] = 0
    for _ in range(iters):
        mu = np.exp(X @ beta + off)
        z = X @ beta + (y - mu) / mu
        W = w * mu
        new = np.linalg.solve(X.T @ (W[:, None] * X) + ridge, X.T @ (W * z))
        if np.max(np.abs(new - beta)) < 1e-8:
            beta = new
            break
        beta = new
    return beta


def design(ads: pd.DataFrame, confounders=CONFOUNDERS) -> np.ndarray:
    d = pd.get_dummies(ads[confounders].astype(str), drop_first=True, dtype=float)
    return np.column_stack([np.ones(len(ads)), d.to_numpy()])


def effects(ads: pd.DataFrame, feats: pd.DataFrame, n_boot: int = N_BOOT, seed: int = SEED,
            confounders=CONFOUNDERS) -> pd.DataFrame:
    """Raw and confounder-adjusted CPA ratios with cluster-bootstrap CIs for every feature column."""
    F = feats.to_numpy(dtype=float)                   # ads × features
    spend = ads.spend_inr.to_numpy(float)
    purch = ads.purchases.to_numpy(float)
    X = design(ads, confounders)

    W = np.vstack([np.ones(len(ads)), m.cluster_bootstrap_weights(ads.cluster, n_boot, seed)])
    expected = np.vstack([poisson_rates(X, purch, spend, w) for w in W])   # (1+B) × ads

    def ratios(Wm, E):
        s_in, s_out = (Wm * spend) @ F, (Wm * spend) @ (1 - F)
        p_in, p_out = (Wm * purch) @ F, (Wm * purch) @ (1 - F)
        e_in, e_out = (Wm * E) @ F, (Wm * E) @ (1 - F)
        with np.errstate(divide="ignore", invalid="ignore"):
            raw = (s_in / p_in) / (s_out / p_out)
            adj = (e_in / p_in) / (e_out / p_out)       # = (actual/expected out) / (actual/expected in)
        return raw, adj

    raw, adj = ratios(W, expected)
    rows = []
    for j, col in enumerate(feats.columns):
        inside = feats[col]
        r_b, a_b = raw[1:, j], adj[1:, j]
        r_b, a_b = r_b[np.isfinite(r_b)], a_b[np.isfinite(a_b)]
        g_in, g_out = m.pooled(ads[inside]), m.pooled(ads[~inside])
        top_share = ads.loc[inside, "spend_inr"].max() / max(g_in["spend_inr"], 1)
        rows.append({
            "feature": col,
            "label": col.split("=")[0] if "=" in col else col,
            "n_with": int(inside.sum()), "n_without": int((~inside).sum()),
            "clusters_with": ads.loc[inside, "cluster"].nunique(),
            "spend_share_with": g_in["spend_inr"] / ads.spend_inr.sum(),
            "largest_ad_share_of_group_spend": top_share,
            "cpa_with": g_in["cpa"], "cpa_without": g_out["cpa"],
            "cpa_ratio_raw": raw[0, j], **ci(r_b, "raw"),
            "cpa_ratio_adj": adj[0, j], **ci(a_b, "adj"),
            "p_adj": boot_p(a_b),
            **{f"{k}_with": g_in[k] for k in ["ctr", "hook_rate", "hold_rate", "atc_rate", "cvr", "roas"]},
            **{f"{k}_without": g_out[k] for k in ["ctr", "hook_rate", "hold_rate", "atc_rate", "cvr", "roas"]},
            "ad_ids_with": ", ".join(ads.loc[inside, "ad_id"]),
        })
    return pd.DataFrame(rows)


def ci(b, tag):
    if len(b) == 0:
        return {f"{tag}_lo95": np.nan, f"{tag}_hi95": np.nan, f"{tag}_lo90": np.nan, f"{tag}_hi90": np.nan}
    return {f"{tag}_lo95": np.quantile(b, 0.025), f"{tag}_hi95": np.quantile(b, 0.975),
            f"{tag}_lo90": np.quantile(b, 0.05), f"{tag}_hi90": np.quantile(b, 0.95)}


def boot_p(b):
    """Two-sided bootstrap p-value for 'ratio = 1'."""
    if len(b) == 0:
        return np.nan
    return min(1.0, 2 * min((b >= 1).mean(), (b <= 1).mean()) + 1 / len(b))


def bh(p: pd.Series) -> pd.Series:
    """Benjamini–Hochberg q-values (NaNs ignored)."""
    ok = p.dropna().sort_values()
    n = len(ok)
    q = (ok * n / np.arange(1, n + 1))[::-1].cummin()[::-1].clip(upper=1)
    return q.reindex(p.index)


def sensitivity(res: pd.DataFrame, ads_alt: pd.DataFrame, level: float):
    """Rerun on an alternative ad set; return (adjusted ratio, holds-with-same-direction flag)."""
    alt = effects(ads_alt, feature_matrix(ads_alt), n_boot=1000).set_index("feature").reindex(res.feature)
    lo = alt.adj_lo95 if level == 0.95 else alt.adj_lo90
    hi = alt.adj_hi95 if level == 0.95 else alt.adj_hi90
    same = np.sign(np.log(alt.cpa_ratio_adj.to_numpy())) == np.sign(np.log(res.cpa_ratio_adj.to_numpy()))
    return alt.cpa_ratio_adj.to_numpy(), excludes_one(lo, hi).to_numpy() & same


def excludes_one(lo, hi):
    return (hi < 1) | (lo > 1)


def verdict(r) -> str:
    if r.label in CONFOUNDERS:
        return "adjusted for (see confounder table)"
    if min(r.n_with, r.n_without) < MIN_N:
        return "not tested (too few ads)"
    same_dir = np.sign(np.log(r.cpa_ratio_raw)) == np.sign(np.log(r.cpa_ratio_adj))
    strong = (min(r.n_with, r.n_without) >= STRONG_MIN_N and same_dir
              and excludes_one(r.raw_lo95, r.raw_hi95) and excludes_one(r.adj_lo95, r.adj_hi95)
              and r.q_adj < FDR_Q and r.robust_to_LJ089 and r.robust_to_top_ad)
    if strong:
        return "strong"
    if same_dir and excludes_one(r.adj_lo90, r.adj_hi90):
        return "suggestive" if r.robust_to_top_ad else "driven by one ad"
    return "inconclusive"


# One feature per theme for the joint model, so overlapping themes don't double-count.
JOINT = ["child_role=reacts_to_taste", "language=English_or_Hinglish", "hook_driver=curiosity_gap",
         "hook_delivered_by=combination", "creator_type=parent_or_caregiver", "narratives=kids_overall_growth",
         "persuasion=authority_science", "humour=any", "child_in_first_3s=yes", "brand_first_said=within_5s"]


def joint_model(ads: pd.DataFrame, feats: pd.DataFrame, n_boot: int = N_BOOT, seed: int = SEED) -> pd.DataFrame:
    """Poisson model of purchases on JOINT features + confounders (log-spend offset).

    exp(-coef) is the CPA multiplier for having the feature, holding the others fixed.
    """
    X = np.column_stack([design(ads), feats[JOINT].to_numpy(float)])
    y, spend = ads.purchases.to_numpy(float), ads.spend_inr.to_numpy(float)
    k = len(JOINT)
    point = poisson_fit(X, y, spend, np.ones(len(ads)))[-k:]
    boots = np.array([poisson_fit(X, y, spend, w)[-k:]
                      for w in m.cluster_bootstrap_weights(ads.cluster, n_boot, seed + 1)])
    mult = np.exp(-boots)
    return pd.DataFrame({
        "feature": JOINT, "n_with": feats[JOINT].sum().to_numpy(),
        "cpa_multiplier": np.exp(-point),
        "lo95": np.quantile(mult, 0.025, axis=0), "hi95": np.quantile(mult, 0.975, axis=0),
        "lo90": np.quantile(mult, 0.05, axis=0), "hi90": np.quantile(mult, 0.95, axis=0),
    })


def confounder_table(ads: pd.DataFrame) -> pd.DataFrame:
    """Product effect adjusted for stop batch only, and stop-batch effect adjusted for product only."""
    out = []
    for conf, other in [("product_form", ["stop_batch"]), ("stop_batch", ["product_form"])]:
        f = pd.DataFrame({f"{conf}={v}": ads[conf] == v for v in sorted(ads[conf].unique())})
        out.append(effects(ads, f, confounders=other))
    return pd.concat(out, ignore_index=True)


def run():
    ads = m.load_ads()
    feats = feature_matrix(ads)
    res = effects(ads, feats)
    res["aliases"] = res.feature.map(lambda f: ", ".join(feats.attrs["aliases"].get(f, [])))
    testable = (np.minimum(res.n_with, res.n_without) >= MIN_N) & ~res.label.isin(CONFOUNDERS)
    res["q_adj"] = bh(res.p_adj.where(testable))

    # Sensitivity 1: put LJ-089 (excluded tracking break) back in. Needs 95% CI to hold.
    ads_all = m.load_ads(include_excluded=True)
    res["cpa_ratio_adj_with_LJ089"], res["robust_to_LJ089"] = sensitivity(res, ads_all, 0.95)

    # Sensitivity 2: drop the single ad with the most purchases (LJ-004: ~29% of purchases).
    # A finding that only exists because of one ad is not a pattern. Needs 90% CI to hold.
    top_ad = ads.loc[ads.purchases.idxmax(), "ad_id"]
    res.attrs["top_ad"] = top_ad
    res[f"cpa_ratio_adj_without_top_ad"], res["robust_to_top_ad"] = sensitivity(
        res, ads[ads.ad_id != top_ad].reset_index(drop=True), 0.90)

    res["verdict"] = res.apply(verdict, axis=1)
    res["direction"] = np.where(res.cpa_ratio_adj < 1, "cheaper", "more expensive")
    order = {"strong": 0, "suggestive": 1, "driven by one ad": 2, "inconclusive": 3,
             "not tested (too few ads)": 4, "adjusted for (see confounder table)": 5}
    res = res.sort_values(["verdict", "cpa_ratio_adj"], key=lambda c: c.map(order) if c.name == "verdict" else c)
    m.OUT.mkdir(exist_ok=True)
    res.to_csv(m.OUT / "phase1_label_effects.csv", index=False)

    joint = joint_model(ads, feats)
    no_top = ads[ads.ad_id != top_ad].reset_index(drop=True)
    j2 = joint_model(no_top, feature_matrix(no_top), n_boot=1000)
    joint["cpa_multiplier_without_top_ad"] = j2.cpa_multiplier.to_numpy()
    joint["lo90_without_top_ad"], joint["hi90_without_top_ad"] = j2.lo90.to_numpy(), j2.hi90.to_numpy()
    joint.to_csv(m.OUT / "phase1_joint_model.csv", index=False)
    conf = confounder_table(ads)
    conf.to_csv(m.OUT / "phase1_confounders.csv", index=False)

    # Overall + per-ad tables for traceability.
    ads_all.to_csv(m.OUT / "phase1_ad_metrics.csv", index=False)
    baseline = pd.Series(m.pooled(ads)).rename("all_ads_ex_LJ089")
    baseline.to_csv(m.OUT / "phase1_account_baseline.csv")
    return res, ads, joint, conf


if __name__ == "__main__":
    pd.set_option("display.width", 220)
    res, ads, joint, conf = run()
    show = res[res.verdict.isin(["strong", "suggestive", "driven by one ad"])][
        ["feature", "verdict", "n_with", "n_without", "cpa_with", "cpa_without", "cpa_ratio_raw",
         "cpa_ratio_adj", "adj_lo95", "adj_hi95", "q_adj", "robust_to_LJ089", "cpa_ratio_adj_without_top_ad"]]
    print(show.round(2).to_string(index=False))
    print("\nverdict counts:", res.verdict.value_counts().to_dict())
