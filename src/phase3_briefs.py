"""Phase 3: creator briefs.

The creative direction in BRIEFS is written by hand (it is a recommendation), but every number in the
rendered briefs is computed here from the data, and every cited ad_id / post_url / claim is checked to
exist. Claims may only come from CLAIMS, and each CLAIMS entry must match the brand's own ads.

Run (after phases 1-2):  python src/phase3_briefs.py
"""
import json
import re

import numpy as np
import pandas as pd

import metrics as m
import phase2_creators as c

# Claims library: (wording for the brief, regex on ads.claims_made, product the claim belongs to or None).
# Only claims the brand already ran. A product-specific claim is measured only on that product's ads and
# compared with that product's average, so a cheap product does not make its claims look good by itself.
CLAIMS = {
    "pm_12g": ("Proteinmix: 12g plant protein in one scoop", r"12\s?g", "proteinmix"),
    "pm_taste": ("Proteinmix: no change in taste or smell of roti / pancakes",
                 r"taste change|taste remains|change the taste|identical to regular", "proteinmix"),
    "pm_source": ("Proteinmix: made from pea, brown rice and soy protein", r"\bpea\b", "proteinmix"),
    "pm_uses": ("Proteinmix: mixes into roti, paratha, dosa, chilla, pancakes", r"roti|dosa|chilla|paratha",
                "proteinmix"),
    "no_sugar": ("No added sugar, no preservatives", r"no added sugar|zero added sugar", None),
    "nm7_eggs": ("Nutrimix 7+: two scoops with milk give almost as much protein as two eggs", r"two eggs|2 eggs",
                 "nutrimix"),
    "nm7_dal": ("A 9-year-old needs at least 24g protein a day, about 7-8 katoris of dal", r"katori", "nutrimix"),
    "nm_source": ("Nutrimix protein comes from skimmed milk powder, almonds and walnuts", r"skim", "nutrimix"),
    "nm2_5g": ("Nutrimix 2+: 5g protein in two scoops", r"5\s?g(?:rams)?\s(?:of\s)?protein|5 gram protein",
               "nutrimix"),
    "nm_sweet": ("Sweetened with jaggery and dates, no artificial sweeteners",
                 r"jaggery(?:,)? and dates|jaggery & dates", "nutrimix"),
    "nm_23": ("23 vitamins and minerals", r"23 (?:essential )?vitamins", "nutrimix"),
    "kids_back": ("Kids keep coming back for more because they love the taste", r"coming back|love the taste",
                  "nutrimix"),
}
THIN_CLAIM_N = 3        # fewer ads than this: "thin evidence"
CLAIM_BAND = 0.10       # within ±10% of the product average: "no better than average"
PRODUCT_NAMES = {"proteinmix": "Proteinmix", "nutrimix": "Nutrimix", None: "the account"}

# Ingredients the briefs are built on (Phase 1): used to pick the comparable ads for the CPA range.
# Lookalikes are taken within the brief's own product, so Proteinmix briefs are compared with Proteinmix ads.
COMPARABLE = "a child reacts to the taste on camera, spoken in English or Hinglish"

BRIEFS = {
    "storiesbyvihaa": dict(
        product="Proteinmix (in Viha's roti / paratha)",
        product_key="proteinmix",
        why_extra=[
            "Viha is the presenter in {child_presenter:.0%} of posts — the child-led format behind LJ-004 "
            "(the account's best ad, {cpa_LJ004} per purchase) and LJ-050.",
            "Her single most-played recent post is Viha trying to speak Hindi in a Telugu accent "
            "({hindi_post_plays} plays), so a Hinglish script plays to an existing strength.",
            "She already films Viha eating and reacting to food (e.g. the restaurant spicy-food reaction, "
            "{food_post_plays} plays).",
            "She has worked with Little Joys before: the audience file lists it among her past-year brands. No ad "
            "in this export names her, so whichever ad that was cannot be identified here; ask the brand team "
            "how it performed before booking.",
        ],
        risks=[
            "Her audience is only {aud_women} women ({aud_men} men; {aud_age}). The buyer is usually a mother, so a "
            "large share of her reach may never buy. This is the only one of the five with audience data, so it "
            "is shown as a risk, not scored. Ask for her current audience split before booking.",
        ],
        hook=('Viha, to camera, holding her plate, in her Telugu-accented Hinglish: "Aaj dekho meri plate mein '
              'kya kya hai!" On screen: "Viha ki roti mein ek secret hai 🤫". Spoken and on-screen together, '
              'as LJ-004 opened.'),
        script=[
            ("0-3s", "Viha with her lunch plate, spoken + text hook (above)."),
            ("3-10s", "Cut to Mom's hands adding one scoop of Proteinmix to the atta; Viha peeks in suspiciously."),
            ("10-20s", "Viha bites the roti, does her signature exaggerated chewing face, then: \"Taste toh bilkul same hai!\" "
                       "This is the core moment — a real child genuinely tasting on camera."),
            ("20-30s", "Mom voiceover (Hinglish): 12g plant protein in one scoop, from pea, brown rice and soy; "
                       "no change in taste."),
            ("30-35s", "Viha asks for a second roti; packshot with \"Little Joys Proteinmix\" on screen."),
        ],
        claims=["pm_taste", "pm_source", "pm_12g"],
        avoid=[
            "An adult script read by Viha about nutrients (her profile: an adult reading marketing copy feels foreign).",
            "Studio lighting; keep the home-video look.",
            "Height / 'overall growth' promises and deficiency fear (both did worse in the ads).",
            "Pure Hindi: the {hindi_n} pure-Hindi ads cost {hindi_cpa} per purchase vs {hinglish_cpa} for Hinglish "
            "(not conclusive, but no reason to risk it). Keep English words in the script.",
            "Telugu as the only version — no Telugu ad has ever been tested; regional-language ads cost "
            "{regional_pct} more per purchase after adjustment.",
        ],
        fmt="30-35s Reel, 9:16, home setting, Hinglish (Hindi-English mix, not pure Hindi). A Telugu cut of "
            "the same video can run as a small side test.",
        ad_refs=["LJ-004", "LJ-056", "LJ-098", "LJ-050"],
        post_refs=["https://www.instagram.com/p/DdfhprMBiO0/", "https://www.instagram.com/p/DdqBtBgqW-q/",
                   "https://www.instagram.com/p/DeIwMiYhtVN/"],
    ),
    "hello_ps8": dict(
        product="Nutrimix 2+ (chocolate milk)",
        product_key="nutrimix",
        why_extra=[
            "Her child (3-7) is on camera in {kids:.0%} of posts, in warm candid moments — her native format is "
            "'a candid interaction with her child, then a natural transition into a product in her routine'.",
            "Safety score {safety:.2f}: no competitor deals and only {spon} sponsored posts in her last 20.",
            "Gap to fix in the brief: a child is shown around food in {food:.0%} of her posts, so the "
            "taste moment must be designed in, not assumed.",
        ],
        hook=('Post-workout, she reaches for her shake — it\'s gone. Text: "Someone stole my protein shake 👀". '
              'Reveal: her child with a chocolate moustache. A curiosity gap (curiosity hooks did better) in her '
              'own fitness-mom world.'),
        script=[
            ("0-3s", "Gym-wear, empty glass, spoken + text hook."),
            ("3-12s", "Reveal the child mid-sip; she asks what's in the glass; the child refuses to give it back."),
            ("12-22s", "She makes the child their own glass: two scoops of Nutrimix 2+ in milk. Child tastes and reacts on camera."),
            ("22-30s", "Voiceover: kids keep asking for it because of the taste. One product fact at most "
                       "(5g protein in two scoops)."),
            ("30-35s", "Close on the two of them clinking glasses; packshot."),
        ],
        claims=["kids_back", "nm2_5g"],
        avoid=[
            "Leading with her own fitness — the child's taste reaction must be the centre (it is the strongest signal).",
            "{template_warning}",
            "Corporate language or a stiff studio set (her profile flags both as foreign).",
            "Overall-growth framing.",
        ],
        fmt="30-35s Reel, bright high-contrast home look, Hinglish voiceover with English text overlays.",
        ad_refs=["LJ-055", "LJ-035", "LJ-009", "LJ-025"],
        post_refs=["https://www.instagram.com/p/DdtrfP4S4Vu/", "https://www.instagram.com/p/Dc00F5_S4Ki/"],
    ),
    "mumma_and_ridhu": dict(
        product="Proteinmix (pancakes) — blind taste test with her two children",
        product_key="proteinmix",
        why_extra=[
            "Two children on camera (ages 3-7 and 8-12) in {kids:.0%} of posts, and children around food in "
            "{food:.0%} — among the highest of the 20.",
            "Her proven format is the problem-solution 'mom hack' demo, which matches the recipe/hack ads "
            "(LJ-056, LJ-076, LJ-097).",
            "Caution: her sponsored videos get {spon_ratio:.0%} of the plays her organic ones get, and "
            "{spon} of her last 20 posts are sponsored.",
        ],
        hook=('Two plates of pancakes. Spoken + text: "Ek pancake mein 12g extra protein hai. Dekhte hain bacche '
              'pakad paate hain ya nahi?" — the exact structure of LJ-056 ({cpa_LJ056} per purchase).'),
        script=[
            ("0-3s", "Two plates, spoken + text hook."),
            ("3-15s", "Both kids taste both pancakes; genuine guessing and reactions — let them disagree."),
            ("15-25s", "Reveal: the Proteinmix one. Her calm direct-to-camera: 12g plant protein in one scoop, "
                       "no change in taste or smell."),
            ("25-35s", "Quick montage: same scoop in roti and chilla; ends on the kids asking for more."),
        ],
        claims=["pm_taste", "pm_uses", "pm_12g"],
        avoid=[
            "Over-polishing with cinematic slow-motion over the tasting — the reaction must look unscripted.",
            "High-pressure sales language (her profile flags it).",
            "Science-explainer framing of protein needs.",
        ],
        fmt="30-40s Reel, warm domestic lighting, Hinglish.",
        ad_refs=["LJ-056", "LJ-098", "LJ-004", "LJ-097"],
        post_refs=["https://www.instagram.com/p/DaiBXLwqFi1/", "https://www.instagram.com/p/DdBwgfXKM2S/"],
    ),
    "the_mum_wife_playbook": dict(
        product="Nutrimix 2+ (chocolate milk) — a skit with her daughter ('Madam')",
        product_key="nutrimix",
        why_extra=[
            "Her daughter (3-7) is on camera in {kids:.0%} of posts, mostly in playful parent-child dialogue skits — "
            "she already talks on camera, so the taste reaction can be spoken.",
            "Her skits occasionally break out ({n_viral} posts above 20M plays), but her median is only {median_plays} — "
            "the most volatile reach of the five.",
            "Caution: her one food sponsorship (a kids' yogurt) got {epigamia_plays} plays, well under her median.",
        ],
        hook=('Text: "Madam ki doodh wali negotiation 🙄". Madam, to camera: "Mumma, doodh nahi piyungi." '
              'Child-first, spoken + on-screen, in her existing Madam-and-Mumma dialogue style.'),
        script=[
            ("0-3s", "Madam's refusal, spoken + text hook."),
            ("3-12s", "Back-and-forth negotiation, her signature repetitive comic dialogue."),
            ("12-22s", "Mumma stirs in two scoops of chocolate Nutrimix 2+; Madam tastes, pauses, and finishes the glass."),
            ("22-30s", "Madam holds out the empty glass: \"Aur?\" Voiceover: kids keep coming back for the taste. "
                       "One product fact at most (5g protein in two scoops)."),
        ],
        claims=["kids_back", "nm2_5g"],
        avoid=[
            "Relying on the joke alone — humour was not a proven ingredient; the taste moment carries the ad.",
            "{template_warning}",
            "Studio lighting or a script without Madam in frame (her profile flags both).",
            "Fear about 'nutrition gaps'.",
        ],
        fmt="25-30s Reel, handheld home video, natural light, Hinglish.",
        ad_refs=["LJ-055", "LJ-035", "LJ-009"],
        post_refs=["https://www.instagram.com/p/DXrlSXEDKMJ/", "https://www.instagram.com/p/DeJUa9bsS-K/",
                   "https://www.instagram.com/p/DeYypNeTkm8/"],
    ),
    "ohmother.in": dict(
        product="Proteinmix (dinner rotis)",
        product_key="proteinmix",
        why_extra=[
            "Children aged 3-12 in {kids:.0%} of her posts, filmed in real-time routines; speaks English on camera.",
            "Her own food post already uses a curiosity hook: \"you won't believe what I'm feeding my kids for "
            "dinner\".",
            "Picked for #5 over the model's #5 (livesimply_withkripa, who has no child of product age) on fit. "
            "The two are close to a tie: under shifted weights each makes the top five about as often "
            "({top5_self} vs {top5_kripa}). Trade-off: small reach (median {median_plays} plays) and sponsored "
            "videos get {spon_ratio:.0%} of organic plays.",
            "Note: she promoted an adult protein supplement (one.science) in October — not a kids-nutrition "
            "competitor, but check exclusivity.",
        ],
        hook=('Her own line, adapted: "The cook cancelled again — and you won\'t believe how much protein I just '
              'hid in tonight\'s rotis." Spoken to camera + on-screen text.'),
        script=[
            ("0-3s", "Direct to camera in the kitchen, spoken + text hook."),
            ("3-12s", "Time-stamped speed montage: one scoop of Proteinmix into the atta, rolling, puffing roti."),
            ("12-22s", "Kids at the table; she asks if they notice anything; they don't — real reactions."),
            ("22-32s", "Voiceover: 12g plant protein in one scoop, no change in taste, made from pea, brown rice "
                       "and soy."),
        ],
        claims=["pm_taste", "pm_source", "pm_12g"],
        avoid=[
            "Adult-protein framing from her one.science post — keep it about the kids.",
            "Scripted, formal delivery; keep the handheld domestic style.",
            "Deficiency or immunity fear, and protein-requirement maths (science framing did not do better).",
        ],
        fmt="30s Reel, handheld kitchen footage, English with a few Hindi words.",
        ad_refs=["LJ-098", "LJ-004", "LJ-071", "LJ-050"],
        post_refs=["https://www.instagram.com/p/DeRBAZvNScx/", "https://www.instagram.com/p/DXtcPVSjX2h/"],
    ),
}


def claims_library(ads: pd.DataFrame, eff: pd.DataFrame) -> pd.DataFrame:
    """Each claim's ads (within its product) and how they did against that product's average."""
    rows = []
    for key, (text, pat, product) in CLAIMS.items():
        scope = ads if product is None else ads[ads["product"] == product]
        hit = scope.claims_made.fillna("").str.contains(pat, case=False, regex=True)
        ids = scope.loc[hit, "ad_id"].tolist()
        e = eff[eff.ad_id.isin(ids) & (eff.purchases >= 20)]
        cpa = m.pooled(scope[hit])["cpa"] if ids else np.nan
        base = m.pooled(scope)["cpa"]
        ratio = cpa / base
        strength = ("thin" if len(ids) < THIN_CLAIM_N else "cheaper" if ratio < 1 - CLAIM_BAND
                    else "costlier" if ratio > 1 + CLAIM_BAND else "average")
        rows.append({"key": key, "claim": text, "product": product or "all", "n_ads": len(ids),
                     "ad_ids": ", ".join(ids), "pooled_cpa_inr": cpa, "product_avg_cpa_inr": base,
                     "ratio_to_product_avg": ratio, "strength": strength,
                     "best_ads": ", ".join(e.sort_values("efficiency", ascending=False).ad_id.head(3))})
    lib = pd.DataFrame(rows).set_index("key")
    assert (lib.n_ads > 0).all(), f"claims not found in any ad: {list(lib.index[lib.n_ads == 0])}"
    return lib


def claim_strength_words(row) -> str:
    who = PRODUCT_NAMES[None if row["product"] == "all" else row["product"]]
    avg = "the account average" if row["product"] == "all" else f"the {who} average"
    n = int(row["n_ads"])
    return {"thin": f"Thin evidence: only {n} ad{'s' if n > 1 else ''} used it",
            "cheaper": f"Ads using it were cheaper than {avg} ({fmt_inr(row['product_avg_cpa_inr'])})",
            "average": f"No better than {avg} ({fmt_inr(row['product_avg_cpa_inr'])}): fine to say, don't lead with it",
            "costlier": f"Ads using it cost more than {avg} ({fmt_inr(row['product_avg_cpa_inr'])}): say it briefly, if at all",
            }[row["strength"]]


def lookalike_mask(ads: pd.DataFrame, product: str) -> pd.Series:
    return (ads.child_role.fillna("").str.contains("reacts_to_taste") & ads.language.isin(["English", "Hinglish"])
            & (ads["product"] == product))


def comparable_cpa(ads: pd.DataFrame, product: str) -> dict:
    """Pooled CPA (90% cluster-bootstrap range) for ads of the same product built like the brief,
    the product's own average, and the same with LJ-004 removed."""
    mask = lookalike_mask(ads, product)
    prod = ads["product"] == product
    out = {"product": product, "ad_ids": ", ".join(ads.ad_id[mask]), "n": int(mask.sum()),
           "per_ad_min": ads.cpa[mask].min(), "per_ad_max": ads.cpa[mask].max(),
           "per_ad_median": ads.cpa[mask].median(), "account_cpa": m.pooled(ads)["cpa"],
           "product_n": int(prod.sum()), "product_cpa": m.pooled(ads[prod])["cpa"],
           "product_cpa_no_LJ004": m.pooled(ads[prod & (ads.ad_id != "LJ-004")])["cpa"],
           "has_LJ004": bool((ads.ad_id[mask] == "LJ-004").any())}
    for tag, g in [("all", ads[mask]), ("no_LJ004", ads[mask & (ads.ad_id != "LJ-004")])]:
        W = m.cluster_bootstrap_weights(g.cluster, 4000, seed=3)
        b = (W * g.spend_inr.to_numpy()).sum(1) / (W * g.purchases.to_numpy()).sum(1)
        out[f"{tag}_cpa"] = m.pooled(g)["cpa"]
        out[f"{tag}_lo90"], out[f"{tag}_hi90"] = np.percentile(b, [5, 95])
    return out


def evidence_context(ads):
    """Numbers quoted inside the hand-written brief text, computed here."""
    eff = pd.read_csv(m.OUT / "phase1_label_effects.csv").set_index("feature")
    t = eff.loc["posthoc:claim_ragi_bajra_jaggery_dates_template"]
    cpa = ads.set_index("ad_id").cpa
    lang = lambda l: m.pooled(ads[ads.language == l])
    return {
        "cpa_LJ004": fmt_inr(cpa["LJ-004"]), "cpa_LJ056": fmt_inr(cpa["LJ-056"]),
        "regional_pct": f"{eff.loc['language=regional_Indian', 'cpa_ratio_adj'] - 1:.0%}",
        "hindi_n": int((ads.language == "Hindi").sum()), "hindi_cpa": fmt_inr(lang("Hindi")["cpa"]),
        "hinglish_cpa": fmt_inr(lang("Hinglish")["cpa"]),
        "template_warning": (f"Listing the ingredient template (ragi, bajra, jaggery, dates, 23 vitamins): the "
                             f"{int(t.n_with)} ads that did cost {fmt_inr(t.cpa_with)} per purchase vs "
                             f"{fmt_inr(t.cpa_without)} for the rest (a pattern spotted after reading the ads, "
                             f"not a proven effect)."),
    }


def creator_context(handle, f, posts, audience, reasons):
    r = f[f.handle == handle].iloc[0]
    p = posts[(posts.handle == handle) & (posts.plays.fillna(0) > 0)]
    q25, q50, q75 = np.percentile(p.plays, [25, 50, 75])
    ratio = r.sponsored_vs_organic_plays
    aud = audience[audience.handle == handle]
    plays = lambda url: f"{posts.loc[posts.post_url == url, 'plays'].iloc[0] / 1e6:.1f}M"
    ctx = {
        "kids": r.kids_3_12_on_camera, "food": r.child_food_moments, "child_presenter": r.child_presenter,
        "spon": int(r.sponsored_posts), "spon_ratio": ratio if pd.notna(ratio) else np.nan,
        "median_plays": f"{q50 / 1000:,.0f}k", "q25": q25, "q75": q75, "followers": r.followers,
        "aud_women": f"{aud.women_pct.iloc[0]:.0f}%" if len(aud) else "n/a",
        "aud_men": f"{aud.men_pct.iloc[0]:.0f}%" if len(aud) else "n/a",
        "aud_age": age_group(aud.age_split.iloc[0]) if len(aud) else "n/a",
        "safety": reasons.loc[handle, "safety"],
        "top5_self": f"{reasons.loc[handle, 'top5_share_local']:.0%}",
        "top5_kripa": f"{reasons.loc['livesimply_withkripa', 'top5_share_local']:.0%}",
        "hindi_post_plays": plays("https://www.instagram.com/p/DdfhprMBiO0/"),
        "food_post_plays": plays("https://www.instagram.com/p/DdqBtBgqW-q/"),
        "n_viral": int((p.plays > 20e6).sum()),
        "epigamia_plays": f"{posts.loc[posts.post_url == 'https://www.instagram.com/p/DeYypNeTkm8/', 'plays'].iloc[0] / 1000:.1f}k",
    }
    return r, ctx


def fmt_inr(x):
    return f"₹{round(x, -1):,.0f}"


def age_group(split: str) -> str:
    """'25-34 44.4%; 18-24 30.5%' -> 'largest age group 25-34, at 44%'."""
    group, pct = split.split(";")[0].split()
    return f"largest age group {group}, at {float(pct.rstrip('%')):.0f}%"


def expected_lines(comp: dict, ctx: dict, spon: str) -> list:
    name = PRODUCT_NAMES[comp["product"]]
    lines = [
        f"No ad by this creator is in the data, so there is no direct measurement. The estimate comes from the "
        f"{comp['n']} {name} ads built the same way ({COMPARABLE}).",
        f"Those ads cost {fmt_inr(comp['all_cpa'])} per purchase together (90% range "
        f"{fmt_inr(comp['all_lo90'])}-{fmt_inr(comp['all_hi90'])}), against {fmt_inr(comp['product_cpa'])} for all "
        f"{comp['product_n']} {name} ads and {fmt_inr(comp['account_cpa'])} for the whole account.",
    ]
    if comp["has_LJ004"]:
        lines.append(f"Without the single best ad (LJ-004) the lookalikes cost {fmt_inr(comp['no_LJ004_cpa'])} "
                     f"({fmt_inr(comp['no_LJ004_lo90'])}-{fmt_inr(comp['no_LJ004_hi90'])}) against "
                     f"{fmt_inr(comp['product_cpa_no_LJ004'])} for {name} overall.")
    gap = comp["all_cpa"] / comp["product_cpa"] - 1
    lines.append(
        f"Individual lookalike ads ranged from {fmt_inr(comp['per_ad_min'])} to {fmt_inr(comp['per_ad_max'])}: "
        f"execution matters as much as the recipe. "
        + (f"Most of the advantage over the account average comes from {name} itself being cheap to sell; the "
           f"format adds about {abs(gap):.0%} on top. "
           if comp["product_cpa"] < comp["account_cpa"] and abs(gap) < 0.25 else
           f"Ads in this format were {abs(gap):.0%} {'cheaper' if gap < 0 else 'dearer'} per purchase than the "
           f"{name} average. ")
        + "Read this as a direction, not a forecast.")
    lines.append(f"Organic reach: their typical video gets {ctx['q25']/1000:,.0f}k-{ctx['q75']/1000:,.0f}k plays; {spon}.")
    return lines


def build_brief(handle, brief, r, ctx, lib, comps, rank_row, ads) -> dict:
    """All brief content with numbers filled in. Markdown and the HTML report both render from this."""
    cpa = ads.set_index("ad_id").cpa
    spon = ("too few sponsored videos to say whether sponsored posts get fewer plays" if pd.isna(ctx["spon_ratio"])
            else f"their sponsored videos have drawn {ctx['spon_ratio']:.0%} of organic plays" if ctx["spon_ratio"] < 1
            else f"their sponsored videos have drawn {ctx['spon_ratio']:.1f}x the plays of organic ones")
    comp = comps[brief["product_key"]]
    return {
        "handle": handle,
        "name": re.split(r"\s*[|]\s*|-\s", r["name"])[0].strip().title(),
        "product": brief["product"], "product_key": brief["product_key"],
        "model_rank": int(rank_row["rank"]), "chosen_over_model": bool(rank_row["rank"] > 5),
        "total": rank_row.total, "fit": rank_row.fit, "reach": rank_row.reach, "safety": rank_row.safety,
        "top5_share": rank_row.top5_share_local, "robustness": rank_row.robustness,
        "followers": int(r.followers), "reach_q25": ctx["q25"], "reach_q75": ctx["q75"],
        "why": [line.format(**ctx) for line in brief["why_extra"]]
               + [f"Followers {r.followers:,}; typical video reach {ctx['q25']/1000:,.0f}k-{ctx['q75']/1000:,.0f}k "
                  f"plays (middle half of their last {int(r.video_posts)} videos)."],
        "risks": [line.format(**ctx) for line in brief.get("risks", [])],
        "hook": brief["hook"].format(**ctx),
        "script": [list(x) for x in brief["script"]],
        "claims": [{"text": lib.loc[k, "claim"], "n_ads": int(lib.loc[k, "n_ads"]),
                    "cpa": fmt_inr(lib.loc[k, "pooled_cpa_inr"]), "strength": lib.loc[k, "strength"],
                    "strength_words": claim_strength_words(lib.loc[k]),
                    "examples": lib.loc[k, "best_ads"] or lib.loc[k, "ad_ids"]} for k in brief["claims"]],
        "avoid": [a.format(**ctx) for a in brief["avoid"]],
        "format": brief["fmt"],
        "expected": expected_lines(comp, ctx, spon),
        "ad_refs": [{"ad_id": a, "cpa": fmt_inr(cpa[a])} for a in brief["ad_refs"]],
        "post_refs": brief["post_refs"],
    }


def to_markdown(d: dict) -> str:
    L = [f"## {d['name']} — @{d['handle']}", "", f"**Product:** {d['product']}  ",
         f"**Score:** {d['total']:.2f} (fit {d['fit']:.2f} · reach {d['reach']:.2f} · safety {d['safety']:.2f}) — "
         f"model rank #{d['model_rank']}, in the top 5 in {d['top5_share']:.0%} of weight perturbations "
         f"({d['robustness']})" + (" — **chosen by the decision-maker over the model's #5**" if d["chosen_over_model"] else ""),
         "", "### Why them", ""] + [f"- {w}" for w in d["why"]]
    if d["risks"]:
        L += ["", "### Risk to check first", ""] + [f"- {w}" for w in d["risks"]]
    L += ["", "### Suggested hook", "", d["hook"], "", "### Script outline", "", "| Time | Beat |", "|---|---|"]
    L += [f"| {t} | {beat} |" for t, beat in d["script"]]
    L += ["", "### Claims to make (all already used in Little Joys ads)", ""]
    L += [f"- {c['text']} — used in {c['n_ads']} ad{'s' if c['n_ads'] > 1 else ''} (together {c['cpa']} per "
          f"purchase), e.g. {c['examples']}. {c['strength_words']}." for c in d["claims"]]
    L += ["", "### What to avoid", ""] + [f"- {a}" for a in d["avoid"]]
    L += ["", "### Format", "", d["format"], "", "### Expected performance (and how sure we are)", ""]
    L += [f"- {e}" for e in d["expected"]]
    L += ["", "### Evidence links", "",
          "- Ads: " + ", ".join(f"{a['ad_id']} ({a['cpa']}/purchase)" for a in d["ad_refs"]),
          "- Creator posts: " + ", ".join(d["post_refs"]), ""]
    return "\n".join(L)


def run():
    ads = m.load_ads()
    eff = pd.read_csv(m.OUT / "phase1_ad_efficiency.csv")
    creators, posts, audience, brands = c.load()
    f = pd.read_csv(m.OUT / "phase2_creator_features.csv", index_col=0)
    reasons = pd.read_csv(m.OUT / "phase2_reasons.csv", index_col=0).set_index("handle")
    lib = claims_library(ads, eff)
    comps = {p: comparable_cpa(ads, p) for p in {b["product_key"] for b in BRIEFS.values()}}

    for h, b in BRIEFS.items():   # every citation must exist
        assert set(b["ad_refs"]) <= set(ads.ad_id), h
        assert set(b["post_refs"]) <= set(posts.post_url[posts.handle == h]), h
        assert set(b["claims"]) <= set(lib.index), h

    parts = ["# Creator briefs — Little Joys", "",
             "Five creators, in score order. Every number below is computed by `src/phase3_briefs.py` from the "
             "raw CSVs; claims are limited to ones Little Joys has already run in its ads.", ""]
    built = []
    for h, b in BRIEFS.items():
        r, ctx = creator_context(h, f, posts, audience, reasons)
        ctx.update(evidence_context(ads))
        built.append(build_brief(h, b, r, ctx, lib, comps, reasons.loc[h], ads))
    parts += [to_markdown(d) for d in built]
    (m.OUT / "phase3_briefs.md").write_text("\n".join(parts), encoding="utf-8")
    (m.OUT / "phase3_briefs.json").write_text(json.dumps(built, indent=1, ensure_ascii=False, default=float),
                                              encoding="utf-8")
    lib.to_csv(m.OUT / "phase3_claims_library.csv")
    pd.DataFrame(comps).to_csv(m.OUT / "phase3_comparable_ads.csv")
    return lib, comps


if __name__ == "__main__":
    pd.set_option("display.width", 250)
    lib, comps = run()
    print(lib[["claim", "product", "n_ads", "pooled_cpa_inr", "product_avg_cpa_inr", "strength"]].round(0).to_string())
    print(pd.DataFrame(comps).to_string())
