"""Phase 3: creator briefs.

The creative direction in BRIEFS is written by hand (it is a recommendation), but every number in the
rendered briefs is computed here from the data, and every cited ad_id / post_url / claim is checked to
exist. Claims may only come from CLAIMS, and each CLAIMS entry must match the brand's own ads.

Run (after phases 1-2):  python src/phase3_briefs.py
"""
import re

import numpy as np
import pandas as pd

import metrics as m
import phase2_creators as c

# Claims library: (wording for the brief, regex on ads.claims_made). Only claims the brand already ran.
CLAIMS = {
    "pm_12g": ("Proteinmix: 12g plant protein in one scoop", r"12\s?g"),
    "pm_taste": ("Proteinmix: no change in taste or smell of roti / pancakes",
                 r"taste change|taste remains|change the taste|identical to regular"),
    "pm_source": ("Proteinmix: made from pea, brown rice and soy protein", r"\bpea\b"),
    "pm_uses": ("Proteinmix: mixes into roti, paratha, dosa, chilla, pancakes", r"roti|dosa|chilla|paratha"),
    "no_sugar": ("No added sugar, no preservatives", r"no added sugar|zero added sugar"),
    "nm7_eggs": ("Nutrimix 7+: two scoops with milk give almost as much protein as two eggs", r"two eggs|2 eggs"),
    "nm7_dal": ("A 9-year-old needs at least 24g protein a day, about 7-8 katoris of dal", r"katori"),
    "nm_source": ("Nutrimix protein comes from skimmed milk powder, almonds and walnuts", r"skim"),
    "nm2_5g": ("Nutrimix 2+: 5g protein in two scoops", r"5\s?g(?:rams)?\s(?:of\s)?protein|5 gram protein"),
    "nm_sweet": ("Sweetened with jaggery and dates, no artificial sweeteners",
                 r"jaggery(?:,)? and dates|jaggery & dates"),
    "nm_23": ("23 vitamins and minerals", r"23 (?:essential )?vitamins"),
    "kids_back": ("Kids keep coming back for more because they love the taste", r"coming back|love the taste"),
}

# Ingredients the briefs are built on (Phase 1): used to pick the comparable ads for the CPA range.
COMPARABLE = "child reacts to taste on camera + English/Hinglish + milk-mix product"

BRIEFS = {
    "storiesbyvihaa": dict(
        product="Proteinmix (in Viha's roti / paratha)",
        why_extra=[
            "Viha is the presenter in {child_presenter:.0%} of posts — the child-led format behind LJ-004 "
            "(the account's best ad, {cpa_LJ004} per purchase) and LJ-050.",
            "Her single most-played recent post is Viha trying to speak Hindi in a Telugu accent "
            "({hindi_post_plays} plays), so a Hindi script plays to an existing strength rather than "
            "against her voice.",
            "She already films Viha eating and reacting to food (e.g. the restaurant spicy-food reaction, "
            "{food_post_plays} plays).",
            "Bonus signal (not scored): the audience file lists Little Joys among her past-year brands, and "
            "her audience is {aud_women} women.",
        ],
        hook=('Viha, to camera, holding her plate, in her Telugu-accented Hindi: "Aaj dekho meri plate mein kya '
              'kya hai!" On screen: "Viha ki roti mein ek secret hai 🤫". Spoken and on-screen together '
              '(LJ-004 opened the same way; ads with a spoken + on-screen hook did better).'),
        script=[
            ("0-3s", "Viha with her lunch plate, spoken + text hook (above)."),
            ("3-10s", "Cut to Mom's hands adding one scoop of Proteinmix to the atta; Viha peeks in suspiciously."),
            ("10-20s", "Viha bites the roti, does her signature exaggerated chewing face, then: \"Taste toh bilkul same hai!\" "
                       "This is the core moment — a real child genuinely tasting on camera."),
            ("20-30s", "Mom voiceover (Hinglish): 12g plant protein in one scoop, from pea, brown rice and soy; no added "
                       "sugar, no preservatives."),
            ("30-35s", "Viha asks for a second roti; packshot with \"Little Joys Proteinmix\" on screen."),
        ],
        claims=["pm_12g", "pm_taste", "pm_source", "no_sugar"],
        avoid=[
            "An adult script read by Viha about nutrients (her profile: an adult reading marketing copy feels foreign).",
            "Studio lighting; keep the home-video look.",
            "Height / 'overall growth' promises and deficiency fear (both did worse in the ads).",
            "Telugu as the only version — no Telugu ad has ever been tested; regional-language ads cost {regional_ratio:.1f}x as much per purchase.",
        ],
        fmt="30-35s Reel, 9:16, home setting, Hindi/Hinglish. Produce a Telugu cut of the same video as an A/B test.",
        ad_refs=["LJ-004", "LJ-056", "LJ-098", "LJ-050"],
        post_refs=["https://www.instagram.com/p/DdfhprMBiO0/", "https://www.instagram.com/p/DdqBtBgqW-q/",
                   "https://www.instagram.com/p/DeIwMiYhtVN/"],
    ),
    "hello_ps8": dict(
        product="Nutrimix 2+ (chocolate milk)",
        why_extra=[
            "Her child (3-7) is on camera in {kids:.0%} of posts, in warm candid moments — her native format is "
            "'a candid interaction with her child, then a natural transition into a product in her routine'.",
            "Highest safety score of the five: no competitor deals and only {spon} sponsored posts in her last 20.",
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
            ("22-30s", "Voiceover: kids keep asking for it because of the taste; 5g protein in two scoops."),
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
                       "no change in taste or smell, no added sugar."),
            ("25-35s", "Quick montage: same scoop in roti and chilla; ends on the kids asking for more."),
        ],
        claims=["pm_12g", "pm_taste", "pm_uses", "no_sugar"],
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
            ("22-30s", "Madam holds out the empty glass: \"Aur?\" Voiceover: kids keep coming back for the taste; "
                       "5g protein in two scoops."),
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
        product="Proteinmix (dinner rotis); Nutrimix 7+ as a second post for her older daughter",
        why_extra=[
            "Children aged 3-12 in {kids:.0%} of her posts, filmed in real-time routines; speaks English on camera.",
            "Her own food post already uses a curiosity hook: \"you won't believe what I'm feeding my kids for "
            "dinner\".",
            "Picked for #5 over the model's choice (livesimply_withkripa, no child of product age) on fit. "
            "Trade-off: small reach (median {median_plays} plays) and sponsored videos get {spon_ratio:.0%} of "
            "organic plays.",
            "Note: she promoted an adult protein supplement (one.science) in October — not a kids-nutrition "
            "competitor, but check exclusivity.",
        ],
        hook=('Her own line, adapted: "The cook cancelled again — and you won\'t believe how much protein I just '
              'hid in tonight\'s rotis." Spoken to camera + on-screen text.'),
        script=[
            ("0-3s", "Direct to camera in the kitchen, spoken + text hook."),
            ("3-12s", "Time-stamped speed montage: one scoop of Proteinmix into the atta, rolling, puffing roti."),
            ("12-22s", "Kids at the table; she asks if they notice anything; they don't — real reactions."),
            ("22-32s", "Voiceover: 12g plant protein in one scoop, no change in taste, made from pea, brown rice and soy. "
                       "Optional line for the older child: a 9-year-old needs 24g protein a day, about 7-8 katoris of dal."),
        ],
        claims=["pm_12g", "pm_taste", "pm_source", "nm7_dal"],
        avoid=[
            "Adult-protein framing from her one.science post — keep it about the kids.",
            "Scripted, formal delivery; keep the handheld domestic style.",
            "Deficiency or immunity fear.",
        ],
        fmt="30s Reel, handheld kitchen footage, English with a few Hindi words.",
        ad_refs=["LJ-098", "LJ-004", "LJ-071", "LJ-050"],
        post_refs=["https://www.instagram.com/p/DeRBAZvNScx/", "https://www.instagram.com/p/DXtcPVSjX2h/"],
    ),
}


def claims_library(ads: pd.DataFrame, eff: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for key, (text, pat) in CLAIMS.items():
        hit = ads.claims_made.fillna("").str.contains(pat, case=False, regex=True)
        ids = ads.loc[hit, "ad_id"].tolist()
        e = eff[eff.ad_id.isin(ids) & (eff.purchases >= 20)]
        rows.append({"key": key, "claim": text, "n_ads": len(ids), "ad_ids": ", ".join(ids),
                     "pooled_cpa_inr": m.pooled(ads[hit])["cpa"] if ids else np.nan,
                     "best_ads": ", ".join(e.sort_values("efficiency", ascending=False).ad_id.head(3))})
    lib = pd.DataFrame(rows).set_index("key")
    assert (lib.n_ads > 0).all(), f"claims not found in any ad: {list(lib.index[lib.n_ads == 0])}"
    return lib


def comparable_cpa(ads: pd.DataFrame) -> dict:
    """Pooled CPA (90% cluster-bootstrap range) for ads built like the briefs, with and without LJ-004."""
    mask = (ads.child_role.fillna("").str.contains("reacts_to_taste") & ads.language.isin(["English", "Hinglish"])
            & (ads.product_form == "milk_mix_powder"))
    out = {"ad_ids": ", ".join(ads.ad_id[mask]), "n": int(mask.sum()),
           "per_ad_min": ads.cpa[mask].min(), "per_ad_max": ads.cpa[mask].max(),
           "per_ad_median": ads.cpa[mask].median(), "account_cpa": m.pooled(ads)["cpa"]}
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
    return {
        "cpa_LJ004": fmt_inr(cpa["LJ-004"]), "cpa_LJ056": fmt_inr(cpa["LJ-056"]),
        "regional_ratio": eff.loc["language=regional_Indian", "cpa_ratio_adj"],
        "template_warning": (f"Listing the ingredient template (ragi, bajra, jaggery, dates, 23 vitamins): the "
                             f"{int(t.n_with)} ads that did cost {fmt_inr(t.cpa_with)} per purchase vs "
                             f"{fmt_inr(t.cpa_without)} for the rest."),
    }


def creator_context(handle, f, posts, audience):
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
        "hindi_post_plays": plays("https://www.instagram.com/p/DdfhprMBiO0/"),
        "food_post_plays": plays("https://www.instagram.com/p/DdqBtBgqW-q/"),
        "n_viral": int((p.plays > 20e6).sum()),
        "epigamia_plays": f"{posts.loc[posts.post_url == 'https://www.instagram.com/p/DeYypNeTkm8/', 'plays'].iloc[0] / 1000:.1f}k",
    }
    return r, ctx


def fmt_inr(x):
    return f"₹{round(x, -1):,.0f}"


def render(handle, brief, r, ctx, lib, comp, rank_row, ads):
    name = re.split(r"\s*[|]\s*|-\s", r["name"])[0].strip().title()
    L = [f"## {name} — @{handle}", "",
         f"**Product:** {brief['product']}  ",
         f"**Score:** {rank_row.total:.2f} (fit {rank_row.fit:.2f} · reach {rank_row.reach:.2f} · safety "
         f"{rank_row.safety:.2f}) — model rank #{rank_row['rank']}, in the top 5 in "
         f"{rank_row.top5_share_local:.0%} of weight perturbations ({rank_row.robustness})"
         + (" — **chosen by the decision-maker over the model's #5**" if rank_row["rank"] > 5 else ""),
         "", "### Why them", ""]
    L += [f"- {line.format(**ctx)}" for line in brief["why_extra"]]
    brief = {**brief, "hook": brief["hook"].format(**ctx), "avoid": [a.format(**ctx) for a in brief["avoid"]]}
    L += [f"- Followers {r.followers:,}; typical video reach {ctx['q25']/1000:,.0f}k-{ctx['q75']/1000:,.0f}k plays "
          f"(middle half of their last {int(r.video_posts)} videos).", "",
          "### Suggested hook", "", brief["hook"], "", "### Script outline", ""]
    L += [f"| {t} | {beat} |" if i else f"| Time | Beat |\n|---|---|\n| {t} | {beat} |"
          for i, (t, beat) in enumerate(brief["script"])]
    L += ["", "### Claims to make (all already used in Little Joys ads)", ""]
    L += [f"- {lib.loc[k, 'claim']} — used in {lib.loc[k, 'n_ads']} ad{'s' if lib.loc[k, 'n_ads'] > 1 else ''} "
          f"(together {fmt_inr(lib.loc[k, 'pooled_cpa_inr'])} per purchase), e.g. "
          f"{lib.loc[k, 'best_ads'] or lib.loc[k, 'ad_ids']}" for k in brief["claims"]]
    L += ["", "### What to avoid", ""] + [f"- {a}" for a in brief["avoid"]]
    L += ["", "### Format", "", brief["fmt"], "", "### Expected performance (and how sure we are)", "",
          f"- **No ad by this creator exists**, so there is no direct measurement. The estimate comes from the "
          f"{comp['n']} Little Joys ads built the same way ({COMPARABLE}).",
          f"- Those ads cost {fmt_inr(comp['all_cpa'])} per purchase together (90% range "
          f"{fmt_inr(comp['all_lo90'])}-{fmt_inr(comp['all_hi90'])}), versus {fmt_inr(comp['account_cpa'])} for the "
          f"whole account. Without the single best ad (LJ-004) it is {fmt_inr(comp['no_LJ004_cpa'])} "
          f"({fmt_inr(comp['no_LJ004_lo90'])}-{fmt_inr(comp['no_LJ004_hi90'])}).",
          f"- Individual ads in that group ranged from {fmt_inr(comp['per_ad_min'])} to {fmt_inr(comp['per_ad_max'])}: "
          f"execution matters as much as the recipe. Read this as 'likely at or better than the account average', "
          f"not a forecast.",
          f"- Organic reach: their typical video gets {ctx['q25']/1000:,.0f}k-{ctx['q75']/1000:,.0f}k plays"
          + ((f"; their sponsored videos have drawn {ctx['spon_ratio']:.0%} of organic plays." if ctx["spon_ratio"] < 1
              else f"; their sponsored videos have drawn {ctx['spon_ratio']:.1f}x the plays of organic ones.")
             if pd.notna(ctx["spon_ratio"])
             else "; too few sponsored videos to say whether sponsored posts get fewer plays."),
          "", "### Evidence links", "",
          "- Ads: " + ", ".join(f"{a} ({fmt_inr(ads.set_index('ad_id').cpa[a])}/purchase)" for a in brief["ad_refs"]),
          "- Creator posts: " + ", ".join(brief["post_refs"]), ""]
    return "\n".join(L)


def run():
    ads = m.load_ads()
    eff = pd.read_csv(m.OUT / "phase1_ad_efficiency.csv")
    creators, posts, audience, brands = c.load()
    f = pd.read_csv(m.OUT / "phase2_creator_features.csv", index_col=0)
    reasons = pd.read_csv(m.OUT / "phase2_reasons.csv", index_col=0).set_index("handle")
    lib = claims_library(ads, eff)
    comp = comparable_cpa(ads)

    for h, b in BRIEFS.items():   # every citation must exist
        assert set(b["ad_refs"]) <= set(ads.ad_id), h
        assert set(b["post_refs"]) <= set(posts.post_url[posts.handle == h]), h
        assert set(b["claims"]) <= set(lib.index), h

    parts = ["# Creator briefs — Little Joys", "",
             "Five creators, in score order. Every number below is computed by `src/phase3_briefs.py` from the "
             "raw CSVs; claims are limited to ones Little Joys has already run in its ads.", ""]
    for h, b in BRIEFS.items():
        r, ctx = creator_context(h, f, posts, audience)
        ctx.update(evidence_context(ads))
        parts.append(render(h, b, r, ctx, lib, comp, reasons.loc[h], ads))
    (m.OUT / "phase3_briefs.md").write_text("\n".join(parts), encoding="utf-8")
    lib.to_csv(m.OUT / "phase3_claims_library.csv")
    pd.Series(comp).to_csv(m.OUT / "phase3_comparable_ads.csv")
    return lib, comp


if __name__ == "__main__":
    pd.set_option("display.width", 250)
    lib, comp = run()
    print(lib[["claim", "n_ads", "pooled_cpa_inr", "best_ads"]].round(0).to_string())
    print(comp)
