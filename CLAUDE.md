# Little Joys — creator selection (galvor.ai take-home)

## Goal
Answer, from the brand's own data only: **"Which 5 of these 20 creators should Little Joys work with
next, and what should each of them say?"** The reader is a non-technical marketing manager who must be
able to follow and trust the reasoning. Nothing we build may mislead them.

The user is the decision-maker. Work in phases (0 audit → 1 ad winners → 2 creator scoring → 3 briefs →
4 deliverable) and STOP for review at the end of each. Ask before any assumption that changes the answer.

## The one hard rule
**Every number shown to the user must trace back to a file + calculation.** Concretely:
- Numbers in the report are produced by code in `src/` from `data/*.csv`, never typed by hand.
- Each claim in the report cites its source: `ad_id`s, `post_url`s, or the output table it came from.
- If the data can't support a claim, say so. Do not fill gaps with marketing intuition.

## Data caveats (first-class constraints)
- **Small n: 100 ads.** Every "X works better" claim carries n, an uncertainty range (bootstrap CI),
  and a verdict: strong / suggestive / inconclusive. Never present a pattern from a handful of ads as a finding.
- **Labels are AI-generated, "mostly right".** Spot-check any label we rely on against transcripts and
  report the error rate. Drop or caveat unreliable labels.
- **Performance numbers are synthetic** but are treated as the real ad-account export.
- **Audience data exists for 3/20 creators** (CR-14, CR-15, CR-20). Bonus signal only; must not move the
  ranking. CR-14's audience is Facebook, not Instagram.
- **Hidden likes**: some accounts show 0 or tiny like counts. Don't penalise; use plays/comments/reshares
  or within-creator medians that exclude hidden-like posts.
- **days_live** is counted up to 26 Oct 2026. README says blank `stopped_date` = still live, BUT in this
  file every ad has a stopped_date (see `outputs/audit.txt`). Stops cluster on 8 dates → batch decisions.
- Known data anomalies (from Phase 0 audit): 3 pairs of ads share a video (LJ-073/093, LJ-036/056,
  LJ-003/059); LJ-089 has ₹4.3L spend, 1,544 add-to-carts and 0 purchases; LJ-001 and LJ-035 have
  blank core labels; revenue ≈ purchases × near-constant AOV (≈₹645; gummies ≈₹564).

## Layout
```
data/            raw CSVs + README (read-only; never modified)
src/             analysis code (one module per phase), pure functions where possible
outputs/         generated tables / audit text / report (regenerable, not hand-edited)
tests/           pytest checks for metric calculations
docs/prompts.md  running log of user prompts and decisions/overrides (append every phase)
```

## Coding conventions
- Python 3.14, pandas / numpy / scipy. Add a dependency only when it earns its place; record it in
  `requirements.txt`.
- Run scripts as `python src/<module>.py` from the repo root (modules import each other from `src/`).
  Paths are resolved relative to the repo root.
- Metric definitions live in one place (`src/metrics.py`) and are unit-tested.
- Ratios across groups are **spend-weighted / pooled** (sum numerator ÷ sum denominator), not means of
  per-ad ratios. Uncertainty via bootstrap resampling of creative clusters (same video_url, or
  transcripts >= 80% similar, count as one creative: 94 clusters from all 100 ads, 93 from the 99 analysed).
- Phase 1 analysis set excludes LJ-089 (decision 2); every finding is re-checked with LJ-089 back in,
  and with LJ-004 (29% of all purchases) removed. A finding that disappears without LJ-004 is labelled
  "driven by one ad".
- Confounders adjusted for in every comparison: stop batch and **product read from the ad text**
  (`metrics.products`: Proteinmix ≈ ₹190 CPA, Nutrimix ≈ ₹490, gummies ≈ ₹570, other ≈ ₹650). Do not use
  the AI `product_form` label for this: it files 13 of 18 Proteinmix ads as "other". Every finding is
  also re-checked with launch period instead of stop batch (`LAUNCH_CONFOUNDERS`).
- Hand annotations (label spot-checks, the full reacts_to_taste check) live in `annotations/` and are
  the only hand-entered data. `metrics.load_ads()` applies the reacts_to_taste corrections by default;
  `corrected=False` gives the AI labels as delivered.
- Multi-value label cells are `; `-separated; explode them explicitly.
- Round for display only, at the presentation layer. Show ranges, not false precision.
- Keep weights and thresholds as named constants at the top of the module so they're editable.
- Commit after each phase with a clear message.
