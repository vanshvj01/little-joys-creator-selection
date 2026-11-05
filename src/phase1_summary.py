"""Phase 1 summary: the ranked "winning ingredients" list, built only from phase1_* outputs.

Grouping several correlated label features into one plain-language ingredient is a judgement call, so
the grouping is written out explicitly in INGREDIENTS. All numbers come from the CSVs.

Run (after phase1_ads.py):  python src/phase1_summary.py
"""
import pandas as pd

import metrics as m

# (plain-language ingredient, primary feature, supporting features, do/avoid)
INGREDIENTS = [
    ("A child genuinely tastes the product on camera and reacts", "child_role=reacts_to_taste",
     ["text:mentions_taste", "narratives=taste_better_than_other_brands"], "do"),
    ("A child presents the ad (child-led)", "creator_type=child_presenter", ["ad_format=child_led"], "do"),
    ("Spoken in English or Hinglish", "language=English_or_Hinglish", [], "do"),
    ("Hook opens a curiosity gap", "hook_driver=curiosity_gap", [], "do"),
    ("Hook is both spoken and shown as on-screen text", "hook_delivered_by=combination", [], "do"),
    ("'Taste unchanged / kids can't tell' claim", "posthoc:claim_taste_unchanged_or_kids_cant_tell", [], "do"),
    ("Science / authority persuasion (explainers, lab talk)", "persuasion=authority_science", [], "avoid"),
    ("Parent's personal-experience hook", "hook_driver=personal_experience", [], "avoid"),
    ("'Overall growth' as the message", "narratives=kids_overall_growth", ["main_benefit=overall_growth"], "avoid"),
    ("Fear / deficiency appeal", "persuasion=fear_appeal", [], "avoid"),
    ("Regional-language voiceover (Kannada, Malayalam, Tamil, Punjabi)", "language=regional_Indian", [], "avoid"),
    ("Child visible in the first 3 seconds", "child_in_first_3s=yes", [], "unproven"),
    ("Brand named within the first 5 seconds", "brand_first_said=within_5s", [], "unproven"),
    ("Hook line is a question", "text:hook_line_is_question", [], "unproven"),
    ("Says grams of protein", "text:says_grams_of_protein", [], "unproven"),
    ("Humour", "humour=any", [], "unproven"),
    ("UGC-style production", "production=ugc", [], "unproven"),
    ("25-40 second length", "duration_s=25-40", [], "unproven"),
]


def examples(feature, eff, feats_ads, k=3, best=True):
    ids = feats_ads.split(", ") if isinstance(feats_ads, str) else []
    e = eff[eff.ad_id.isin(ids) & (eff.purchases >= 20)].sort_values("efficiency", ascending=not best)
    return ", ".join(e.ad_id.head(k))


def build() -> pd.DataFrame:
    eff = pd.read_csv(m.OUT / "phase1_ad_efficiency.csv")
    res = pd.read_csv(m.OUT / "phase1_label_effects.csv").set_index("feature")
    joint = pd.read_csv(m.OUT / "phase1_joint_model.csv").set_index("feature")
    rows = []
    for name, feat, support, kind in INGREDIENTS:
        r = res.loc[feat]
        j = joint.loc[feat] if feat in joint.index else None
        rows.append({
            "ingredient": name, "kind": kind, "feature": feat, "verdict": r.verdict,
            "n_ads_with": int(r.n_with), "n_ads_without": int(r.n_without),
            "cpa_with_inr": r.cpa_with, "cpa_without_inr": r.cpa_without,
            "cpa_ratio_adjusted": r.cpa_ratio_adj, "ci95_lo": r.adj_lo95, "ci95_hi": r.adj_hi95,
            "cpa_ratio_without_LJ004": r.cpa_ratio_adj_without_top_ad,
            "joint_model_ratio": None if j is None else j.cpa_multiplier,
            "joint_ci95": None if j is None else f"{j.lo95:.2f}-{j.hi95:.2f}",
            "supporting": "; ".join(f"{s} ({res.loc[s].cpa_ratio_adj:.2f}, {res.loc[s].verdict})" for s in support),
            "click_through_ratio": r.ctr_with / r.ctr_without,
            "hook_rate_ratio": r.hook_rate_with / r.hook_rate_without,
            "purchase_per_click_ratio": r.cvr_with / r.cvr_without,
            "best_example_ads": examples(feat, eff, r.ad_ids_with, best=True),
            "weakest_example_ads": examples(feat, eff, r.ad_ids_with, best=False),
        })
    return pd.DataFrame(rows)


if __name__ == "__main__":
    pd.set_option("display.width", 260)
    out = build()
    out.to_csv(m.OUT / "phase1_winning_ingredients.csv", index=False)
    print(out.drop(columns=["feature", "supporting"]).round(2).to_string(index=False))
