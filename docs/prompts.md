# Prompt & decision log

Running log of the main prompts and the decisions where the user overrode or corrected the assistant.

## Phase 0 — setup & data audit

**Prompt (summary):** Act as engineering + analytics partner. Business question: which 5 of 20 creators
Little Joys should work with next and what each should say, answered from `ads.csv`, `creators.csv`,
`creator_posts.csv`, `creator_audience.csv` only. Work in phases 0–4 and stop at each checkpoint. Phase 0:
audit the data, write CLAUDE.md, propose a stack.

**Done:** `src/audit.py` → `outputs/audit.txt`; CLAUDE.md; this log.

**Open questions raised to the user at the Phase 0 checkpoint:**
1. No ad is still live (every row has a stopped_date) — the "still live = positive signal" assumption can't be used.
2. LJ-089: ₹4.3L spend, 1,544 ATC, 0 purchases — keep, exclude, or flag as a tracking break?
3. Duplicate-video ad pairs — treat as one creative cluster?
4. Primary metric: ROAS vs CPA, given AOV differs by product form.
5. Permission to download a sample of ad MP4s for label spot-checks.
6. Stack choice.

**User decisions (2026-11-05): "Approve defaults"** — i.e.
1. Drop the still-live signal; adjust for stop batch instead.
2. Exclude LJ-089 from headline numbers, show it separately as a probable tracking break, and run a
   sensitivity check with it included.
3. Treat duplicate-video ads as one creative cluster when bootstrapping.
4. Primary metric = spend-weighted CPA; ROAS as a diagnostic.
5. Permission granted to download ~10 ad MP4s for label spot-checks.
6. Stack: Python (pandas/numpy/scipy) + static Jinja2 HTML report + pytest + one-command rebuild.

## Phase 1 — what wins in the brand's ads

**Prompt (summary):** Per-ad funnel metrics, one primary metric, spend-weighted group comparisons with
bootstrap CIs and minimum-n, confounder checks, transcript mining of top/bottom ads with ad_ids, label
spot-check (~15–20) with agreement rate. Output: ranked "winning ingredients" with evidence strength.

**Decisions taken during Phase 1 (assistant-proposed, flagged for user review at checkpoint):**
- Added product_form as a confounder alongside stop batch: milk-mix ads have roughly half the CPA of
  other products, and many creative choices correlate with product.
- Added a leave-LJ-004-out check: one ad holds 29% of all purchases.
- Duplicate creatives widened from "same video_url" to "transcript ≥ 80% similar" after the spot-check
  found LJ-006/LJ-097 are the same script under different video files (3 extra pairs).
- Verdict rules: strong = n≥10 both sides, 95% CI excludes no-effect raw and adjusted, BH q<0.10,
  survives LJ-089 and LJ-004 checks; suggestive = adjusted 90% CI excludes no-effect and survives
  dropping LJ-004; "driven by one ad" otherwise-suggestive but fails that; n<8 not tested.
  Result: no ingredient reaches "strong" (best q = 0.13).
- Post-hoc text features (taste-unchanged claim, ragi/jaggery template, etc.) were added after reading
  top/bottom ads and are labelled "posthoc" — hypothesis-generating only.
- Video spot-check done by viewing frames in the browser (no files downloaded).

**User decision at Phase 1 checkpoint (2026-11-05): "Accept, start Phase 2"** — Phase 1 ingredients,
verdicts and the product/batch adjustment accepted as the basis for creator scoring.

## Phase 2 — creator fit scoring

**Prompt (summary):** Build creator features (engagement robust to hidden likes, consistency, kids on
camera, language, sponsored vs organic, competitor conflicts, audience as bonus only). Score fit / reach /
risk with explicit editable weights, run a sensitivity check, explain the 15 not picked.

**Decisions taken during Phase 2 (assistant-proposed, flagged for user review at checkpoint):**
- Spoken language taken from post transcripts, not the post `language` label: that label matches the
  transcript language in only 17% of transcribed posts (it appears to describe the caption).
- Brand categories (which brands are direct kids-nutrition competitors) are a hand annotation in
  `annotations/brand_categories.csv`; the data doesn't say what a brand sells.
- **Competitor rule (pending user decision):** default set to hard exclusion of any creator with a paid
  direct-competitor post in the last 120 days (6 creators). The penalty-only alternative is computed too.
- Telugu / Gujarati get no language credit (no ad in those languages; regional languages ×2.0 CPA).
- Audience data shown as text only; not in any score.

**User decision at Phase 2 checkpoint (2026-11-05): "Exclude them"** — creators with a paid
direct-competitor post in the last 120 days are excluded (COMPETITOR_RULE = "hard_exclude" confirmed).
