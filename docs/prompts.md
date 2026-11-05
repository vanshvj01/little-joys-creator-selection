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
- Slot #5: user chose **ohmother.in** over livesimply_withkripa (model's #5 by 0.01) on fit grounds —
  ohmother films kids 3-12 in 70% of posts; kripa has no child of product age. User override of model order.
- storiesbyvihaa kept at #1; her brief is written in **Hindi/Hinglish** (her profile lists Hindi as
  native), with the Telugu risk flagged and a Telugu A/B variant suggested.

## Phase 3 — creator briefs
Final five: storiesbyvihaa, hello_ps8, mumma_and_ridhu, the_mum_wife_playbook, ohmother.in.

**Decisions taken during Phase 3 (assistant-proposed, flagged at checkpoint):**
- Product per creator chosen by child age and evidence: Proteinmix for 3 creators (its claims come from
  the cheapest ads: ₹160-290 per purchase), Nutrimix 2+ for 2 (taste-led; its nutrient claims come from
  weaker ads, ₹500 per purchase, so the brief leads with the taste claim and drops the ragi/jaggery
  ingredient-list template).
- Expected performance is given as the CPA range of the 12 ads built the same way (with/without LJ-004)
  plus the creator's typical reach, explicitly not a per-creator forecast.
- Corrected during writing: removed an unsupported "child speaks → cheaper" claim (that feature was
  "driven by one ad" in Phase 1); swapped a weak supporting ad (LJ-043, ₹770) out of a brief.

**User decision at Phase 3 checkpoint (2026-11-05): "Approve, start Phase 4"** — briefs approved as written.

## Phase 4 — deliverable + repo

**Prompt (summary):** Manager-facing answer (top 5 first, per-creator drill-down, "how we know this",
confidence & limitations, sensible rounding and ranges); tests for core metrics; one-command rebuild;
README; one-page NOTE.md; keep this log.

**Decisions taken during Phase 4:**
- Deliverable is a static, self-contained HTML page rendered from the phase outputs by `src/report.py`
  (Jinja2), published as a private claude.ai artifact for sharing. No hand-typed numbers in the template;
  counts like "3 videos ran twice" and "2,000 resamples" are computed.
- Phase 3 briefs refactored to a structured JSON so the Markdown briefs and the report render from the
  same data.
- Correction: the creative-cluster count is 94 for all 100 ads but **93 for the 99 analysed**; the Phase 1
  checkpoint message and CLAUDE.md had said 94 for the 99. Fixed in CLAUDE.md; the report computes it.
- `run_all.py` deletes nothing itself; full rebuild verified by deleting `outputs/` and rerunning.

## Phase 5 — independent review of the finished deliverable

**Prompt (summary):** "Check if this task is completed and verify all things, also recommend changes if
needed." A fresh session reviewed the published report against the assignment and listed trust issues.
The user then said: **"do all the changes needed."**

**Issues the review raised, and what was done:**
1. *The audience data for #1 was presented as a bonus, but it is a red flag* (storiesbyvihaa's audience is
   30% women). → Now a visible "check audience before booking" risk on her card and brief. Still not
   scored (audience data exists for only 3 of 20 creators), as decided in Phase 2.
2. *"No ad by this creator exists" contradicted the audience file*, which lists Little Joys among her
   past-year brands. → Searched every ad's copy, transcript and on-screen text for her or her child's name:
   no match. The brief now says she has worked with the brand, the ad can't be identified in this
   export, and the brand team should be asked how it did.
3. *All five briefs showed the same expected-performance block.* → Lookalike ads are now taken within the
   brief's own product (Proteinmix or Nutrimix) and compared with that product's average.
4. *The headline label was checked on only 9 ads.* → Every one of the 39 ads tagged
   `child_role=reacts_to_taste` was checked against transcripts and video frames
   (`annotations/reacts_to_taste_fullcheck.csv`): 26 yes, 4 no, 9 unclear. The 4 wrong labels are removed
   before analysis (`metrics.correct_labels`); results are shown for AI label / corrected / hand-confirmed
   only, and barely differ. Two "yes" ads (LJ-021, LJ-065) look AI-generated rather than real children; noted.
5. *The lede overstated the finding.* → Lede now gives the range and says "pattern, not proof".
6. *Adjusting for stop date can absorb the effect* (ads are stopped because they did badly). → Added a
   third robustness check that adjusts for launch period instead (`metrics.launch_periods`, 4 equal
   groups). Every "suggestive" finding survives it; shown on the page.
7. *Bootstrap must resample creatives, not rows.* → Already the case (`cluster_bootstrap_weights`); the
   page now says so.
8. *Hindi vs Hinglish.* → Pure-Hindi ads (10) cost ₹780 vs ₹300 for Hinglish (adjusted: 25% dearer,
   inconclusive). The #1 brief is now written in Hinglish, not "Hindi/Hinglish", and lists pure Hindi
   under "avoid". New row in the ingredient table.
9. *Weak claims were recommended.* → Each claim is now measured on its own product's ads and rated
   (thin / cheaper / average / costlier than that product's average). Dropped: the 1-ad "24g protein /
   katoris of dal" line from #5 and "no added sugar" from #1 and #3 (costlier than average). Kept with a
   visible "thin evidence" tag: "kids keep coming back" (2 ads).
10. *Spoken + on-screen hook has a tiny comparison group* (15 ads without it). → Any ingredient with fewer
    than 20 ads on one side now carries a visible "small comparison group" caveat.
11. Polish: "Your pick" → "Analyst's pick"; "only 0% of posts" → "no child in any recent post"; a
    separate, softer chip style for "suggestive"; ad IDs link to their MP4s; ohmother.in vs
    livesimply_withkripa described as a near-tie (36% vs 37% in top five); hello_ps8's "highest safety
    score of the five" was false (the_mum_wife_playbook is higher) and now quotes her score instead.

**Found during the review fixes (not in the original list) — biggest change to the numbers:**
- The AI's `product_form` label files **13 of the 18 Proteinmix ads as "other"** (with sauces and
  spreads), although Proteinmix is by far the cheapest product per purchase (₹190 vs Nutrimix ₹490,
  gummies ₹570). Adjusting for that label let part of the Proteinmix advantage leak into every ingredient
  common in Proteinmix ads (taste tests, child presenters). Product is now read from the ad text
  (`metrics.products`) and used as the confounder. Effects shrink but keep their direction and verdicts:
  child tasting on camera **40% → 27% cheaper** (as published → now) (95% range 5–38% cheaper), and it now holds at 23% without
  LJ-004 instead of collapsing. Best q rises from 0.13 to 0.34; nothing is "strong". Science/authority
  persuasion moves from "rests on one ad" to "inconclusive". The creator ranking does not depend on
  effect sizes, so the five picks are unchanged.
