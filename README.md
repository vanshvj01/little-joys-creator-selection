# Little Joys: which five creators next, and what should they say?

A take-home for galvor.ai. It answers one question using only Little Joys' own data (100 video ads,
20 Instagram creators and their 392 recent posts):

> Which 5 of these 20 creators should we work with next, and what should each of them say?

**The answer:** `outputs/report.html`, a single self-contained page written for a marketing manager. It
gives the top five first, then a brief per creator, the evidence behind each finding, and a section on
confidence and limitations.

## How to run

Python 3.12+ (developed on 3.14).

```bash
pip install -r requirements.txt
```

```bash
python run_all.py
```

`run_all.py` rebuilds every file in `outputs/` from the four CSVs in `data/`, then runs the tests. It
takes a few minutes, mostly the bootstraps. Use `python run_all.py --no-tests` to skip the tests. Each
step can also be run on its own, in order, e.g. `python src/phase2_creators.py`.

## Project structure

```
data/                    raw CSVs + data README (never modified)
annotations/             the only hand-entered data, kept separate so it can be reviewed and edited
  label_spotcheck.csv      sampled checks of AI labels against transcripts and video frames
  reacts_to_taste_fullcheck.csv  all 39 ads tagged "child reacts to taste", checked by hand
  brand_categories.csv     which brands count as kids-nutrition competitors
src/
  metrics.py               metric definitions, creative clustering, cluster bootstrap
  audit.py                 Phase 0: schema, nulls, distributions, anomalies
  phase1_ads.py            Phase 1: ingredient vs cost-per-purchase comparisons + joint model
  spotcheck.py             Phase 1: label agreement rates
  phase1_summary.py        Phase 1: ranked "winning ingredients"
  phase2_creators.py       Phase 2: creator features, fit/reach/safety scores, weight sensitivity
  phase3_briefs.py         Phase 3: claims library and the five briefs
  report.py + templates/   Phase 4: the HTML report
tests/                   metric definitions, creator rules, report-matches-source checks
outputs/                 everything generated (tables, briefs, report); safe to delete and rebuild
docs/prompts.md          log of the prompts and of every decision where the user overrode or chose
NOTE.md                  one page: key choices and what to build next
```

## Method in brief

1. **Audit.** All ads have a stop date, so "still live" carries no signal. LJ-089 (₹4.3L spend, 0
   purchases) is excluded as a probable tracking break. Ads that share a video or a near-identical script
   are treated as one creative, giving 93 independent creatives across the 99 ads analysed.
2. **What wins in the ads.** The primary metric is spend-weighted cost per purchase (CPA). Every label is
   compared with vs without, adjusted for product and stop date with a Poisson model, with 95% ranges from
   a cluster bootstrap and Benjamini–Hochberg correction across about 140 tests. Product is read from the
   ad's own text, because the AI's `product_form` label files most Proteinmix ads as "other". Each finding
   is re-checked with LJ-089 put back, with the top ad (LJ-004, 29% of purchases) removed, and with launch
   date instead of stop date. The verdict rules are in `src/phase1_ads.py`. Nothing reaches "strong". The
   most robust "suggestive" finding is a child tasting the product on camera (about 27% cheaper per
   purchase, 95% range 5–38%).
3. **Labels.** 178 hand checks against transcripts and video frames, including all 39 ads tagged with the
   headline label: 94% agreement. The 4 wrong headline labels are corrected before analysis. The post-level
   language label was unreliable, so transcript language is used instead.
4. **Creators.** Fit with the ingredients (50%), reach (25%) and safety (25%). Weights are named
   constants. Creators with a paid direct-competitor post in the last 120 days are excluded. Robustness
   comes from 5,000 random weight draws plus 8 named scenarios. Audience data (3 of 20 creators) is shown
   but never scored.
5. **Briefs.** Claims come only from `ads.claims_made`, each rated against ads of the same product. Every
   cited ad, post and claim is checked to exist. Expected performance is the CPA range of lookalike ads of
   the same product, not a per-creator forecast.

## The rule this repo follows

Every number shown to a reader comes from a file plus a calculation in `src/`. Hand judgements are kept
in `annotations/` and logged in `docs/prompts.md`.
