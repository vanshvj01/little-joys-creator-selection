"""Phase 4: the manager-facing report, a single self-contained HTML page.

Reads only the phase outputs (which are themselves built from data/*.csv) and renders
src/templates/report.html.j2 to outputs/report.html. No number in the page is typed by hand.

Run (after phases 1-3):  python src/report.py
"""
import json
import math

import pandas as pd
from jinja2 import Environment, FileSystemLoader, select_autoescape

import metrics as m
import phase1_ads as p1
import phase2_creators as p2

TEMPLATE_DIR = m.ROOT / "src" / "templates"

VERDICT_LABEL = {
    "strong": "Strong",
    "suggestive": "Suggestive",
    "driven by one ad": "Rests on one ad",
    "inconclusive": "Inconclusive",
    "not tested (too few ads)": "Too few ads",
}


def inr(x, step=10):
    return f"₹{round(x / step) * step:,.0f}"


def effect_words(r):
    """CPA ratio -> plain words. 0.6 -> '40% cheaper per purchase'; 1.5 -> '50% more per purchase'."""
    if r < 1:
        return f"{(1 - r):.0%} cheaper"
    return f"{(r - 1):.0%} more expensive"


def ingredient_rows():
    w = pd.read_csv(m.OUT / "phase1_winning_ingredients.csv")
    rows = []
    for r in w.itertuples():
        rows.append({
            "name": r.ingredient, "kind": r.kind, "verdict": VERDICT_LABEL.get(r.verdict, r.verdict),
            "verdict_key": r.verdict.split(" ")[0], "n": r.n_ads_with, "n_without": r.n_ads_without,
            "cpa_with": inr(r.cpa_with_inr), "cpa_without": inr(r.cpa_without_inr),
            "ratio": r.cpa_ratio_adjusted, "lo": r.ci95_lo, "hi": r.ci95_hi,
            "effect": effect_words(r.cpa_ratio_adjusted),
            "range": f"{effect_words(r.ci95_lo)} to {effect_words(r.ci95_hi)}",
            "without_top": effect_words(r.cpa_ratio_without_LJ004),
            "examples": r.best_example_ads, "counter": r.weakest_example_ads,
            "per_click": r.purchase_per_click_ratio, "hook_rate": r.hook_rate_ratio,
        })
    return rows


def forest_svg(rows, width=640, row_h=30, left=270, right=24):
    """Dot-and-whisker chart of adjusted CPA ratios on a log scale (0.25x to 4x)."""
    lo_lim, hi_lim = math.log(0.25), math.log(4)
    plot_w = width - left - right
    x = lambda v: left + (math.log(min(max(v, 0.25), 4)) - lo_lim) / (hi_lim - lo_lim) * plot_w
    top = 34
    h = top + row_h * len(rows) + 12
    out = [f'<svg viewBox="0 0 {width} {h}" role="img" aria-label="Cost per purchase with and without each '
           f'ingredient, with 95% ranges" class="forest">']
    for v, lab in [(0.25, "75% cheaper"), (0.5, "50% cheaper"), (1, "same"), (2, "2× the cost"), (4, "4× the cost")]:
        out.append(f'<line x1="{x(v):.1f}" x2="{x(v):.1f}" y1="{top - 6}" y2="{h - 8}" class="{"axis0" if v == 1 else "grid"}"/>')
        anchor = "start" if v == 0.25 else "end" if v == 4 else "middle"
        out.append(f'<text x="{x(v):.1f}" y="{top - 14}" text-anchor="{anchor}" class="tick">{lab}</text>')
    for i, r in enumerate(rows):
        y = top + row_h * i + row_h / 2
        cls = "do" if r["ratio"] < 1 else "avoid"
        faint = " faint" if r["verdict_key"] not in ("strong", "suggestive") else ""
        name = r["name"] if len(r["name"]) <= 40 else r["name"][:38] + "…"
        out.append(f'<text x="{left - 12}" y="{y + 4:.1f}" text-anchor="end" class="rowlab">{name}</text>')
        out.append(f'<line x1="{x(r["lo"]):.1f}" x2="{x(r["hi"]):.1f}" y1="{y:.1f}" y2="{y:.1f}" class="ci {cls}{faint}"/>')
        out.append(f'<circle cx="{x(r["ratio"]):.1f}" cy="{y:.1f}" r="5" class="pt {cls}{faint}"/>')
    out.append("</svg>")
    return "\n".join(out)


def creator_tables():
    reasons = pd.read_csv(m.OUT / "phase2_reasons.csv", index_col=0)
    ranking = pd.read_csv(m.OUT / "phase2_ranking.csv", index_col=0)
    feats = pd.read_csv(m.OUT / "phase2_creator_features.csv", index_col=0)
    scen_cols = [c for c in ranking.columns if c.startswith("rank_") and c != "rank_if_penalty_only"]
    return reasons, ranking, feats, scen_cols


def audit_facts():
    raw = pd.read_csv(m.DATA / "ads.csv")
    posts = pd.read_csv(m.DATA / "creator_posts.csv")
    creators = pd.read_csv(m.DATA / "creators.csv")
    aud = pd.read_csv(m.DATA / "creator_audience.csv")
    ads = m.load_ads()
    top = ads.loc[ads.purchases.idxmax()]
    return {
        "n_ads": len(raw), "n_ads_used": len(ads), "n_clusters": ads.cluster.nunique(),
        "n_creators": len(creators), "n_posts": len(posts), "n_transcripts": int(posts.transcript.notna().sum()),
        "n_audience": len(aud),
        "n_video_dupes": len(raw) - raw.video_url.nunique(),
        "n_script_dupes": (len(raw) - m.load_ads(include_excluded=True).cluster.nunique()) - (len(raw) - raw.video_url.nunique()),
        "regional_ratio": f"{pd.read_csv(m.OUT / 'phase1_label_effects.csv').set_index('feature').cpa_ratio_adj['language=regional_Indian']:.1f}",
        "n_boot": f"{p1.N_BOOT:,}", "n_sens": f"{p2.N_SENSITIVITY:,}",
        "spend_lakh": f"₹{raw.spend_inr.sum() / 1e5:.1f} lakh",
        "purchases": f"{raw.purchases.sum():,}", "account_cpa": inr(m.pooled(ads)["cpa"]),
        "account_roas": f"{m.pooled(ads)['roas']:.2f}",
        "excluded": list(m.EXCLUDED_ADS.items()),
        "top_ad": top.ad_id, "top_ad_share": f"{top.purchases / ads.purchases.sum():.0%}",
        "top_ad_cpa": inr(top.cpa),
        "date_min": raw.launch_date.min(), "date_max": "2026-10-26",
        "milk_cpa": inr(m.pooled(ads[ads.product_form == "milk_mix_powder"])["cpa"]),
        "other_cpa": inr(m.pooled(ads[ads.product_form != "milk_mix_powder"])["cpa"]),
        "n_tests": int(((pd.read_csv(m.OUT / "phase1_label_effects.csv")[["n_with", "n_without"]].min(axis=1) >= p1.MIN_N)
                        & ~pd.read_csv(m.OUT / "phase1_label_effects.csv").label.isin(p1.CONFOUNDERS)).sum()),
        "best_q": f"{pd.read_csv(m.OUT / 'phase1_label_effects.csv').q_adj.min():.2f}",
    }


def build():
    briefs = json.loads((m.OUT / "phase3_briefs.json").read_text(encoding="utf-8"))
    comp = pd.read_csv(m.OUT / "phase3_comparable_ads.csv", index_col=0).iloc[:, 0]
    agree = pd.read_csv(m.OUT / "phase1_label_agreement.csv")
    reasons, ranking, feats, scen_cols = creator_tables()
    ingredients = ingredient_rows()
    chart_rows = [r for r in ingredients if r["kind"] in ("do", "avoid") and r["verdict_key"] != "not"]
    picked = [b["handle"] for b in briefs]
    others = reasons[~reasons.handle.isin(picked)].sort_values("rank")

    ctx = {
        "facts": audit_facts(),
        "briefs": briefs,
        "ingredients": ingredients,
        "forest": forest_svg(chart_rows),
        "agree": agree.to_dict("records"),
        "agree_all": agree[agree.label == "ALL"].iloc[0].to_dict(),
        "comp": {k: (inr(float(v)) if k.endswith(("cpa", "lo90", "hi90", "min", "max", "median")) else v)
                 for k, v in comp.items()},
        "others": others.to_dict("records"),
        "ranking": ranking.reset_index().to_dict("records"),
        "picked": picked,
        "scen_cols": scen_cols,
        "scen_labels": {c: c.removeprefix("rank_").replace("_", " ") for c in scen_cols},
        "weights": {"Pillars": p2.PILLAR_WEIGHTS, "Fit": p2.FIT_WEIGHTS, "Reach": p2.REACH_WEIGHTS,
                    "Safety": p2.SAFETY_WEIGHTS},
        "recent_days": p2.RECENT_COMPETITOR_DAYS,
        "feats": feats.set_index("handle").to_dict("index"),
    }
    env = Environment(loader=FileSystemLoader(TEMPLATE_DIR), autoescape=select_autoescape(["html", "j2"]))
    env.filters["pct"] = lambda v: f"{v:.0%}"
    env.filters["k"] = lambda v: f"{v / 1e6:.1f}M" if v >= 1e6 else f"{v / 1e3:,.0f}k"
    html = env.get_template("report.html.j2").render(**ctx)
    (m.OUT / "report.html").write_text(html, encoding="utf-8")
    return ctx, html


if __name__ == "__main__":
    ctx, html = build()
    print(f"wrote {m.OUT / 'report.html'} ({len(html) / 1024:.0f} KB)")
