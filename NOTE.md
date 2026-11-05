# Note: key choices, and what I'd build next

## Key choices and why

- **Cost per purchase (CPA) as the one success metric.** Revenue is purchases × an almost fixed order
  value (correlation 0.999), so ROAS adds no information. It also penalises gummies, whose orders are
  smaller (₹564 vs ₹650 for milk mix). CPA answers "what did a sale cost us". CTR, hook rate, hold rate and
  add-to-cart rate are kept as diagnostics. They showed that the winning ingredients act after the click,
  not on attention.
- **Adjust for product and stop date, with product read from the ad itself.** Products differ about 3x in
  cost per purchase (Proteinmix ₹190, Nutrimix ₹490, gummies ₹570), and ads stopped in the same week
  converted alike. The AI's `product_form` label filed 13 of 18 Proteinmix ads as "other", which let the
  cheap product inflate every ingredient common in its ads, so product comes from each ad's text. Fixing
  this cut the headline effect from 40% to 27% cheaper; it found the biggest error in the first version.
- **Three robustness checks on every finding:** the excluded ad put back, the single best ad (LJ-004)
  removed, and launch date used instead of stop date (an ad is often stopped because it did badly, so the
  stop date partly reflects the result). All "suggestive" findings pass all three.
- **A conservative verdict rule, kept after seeing the results.** Nothing reached "strong" (best q = 0.13
  against a 0.10 bar). I kept the bar rather than lower it, and say so plainly. "Suggestive" also has to
  survive removing LJ-004, the single ad behind 29% of purchases.
- **Count creatives, not ads.** Three videos ran twice and three scripts were near-copies. Resampling them
  as one creative stops a reused video from counting as two pieces of evidence.
- **Check the labels before using them.** 94% agreement over 178 hand checks, including all 39 ads tagged
  with the headline label (4 wrong, removed before analysis; the result barely moves either way). The
  post-level `language` label matched spoken language only 17% of the time, so creator language fit uses
  transcripts instead.
- **Fit weighs the most** (50%) because what the creator can deliver is the only link between the ad
  evidence and a creator. Reach and safety are 25% each. Weights are constants, and the top three hold in
  ≥89% of 5,000 random reweightings.
- **Hard exclusion for recent competitor deals** (the user's decision). A creator who sold Gritzo a month
  ago is not a credible Nutrimix voice and may be under exclusivity. This removes two otherwise strong
  creators (sia_3vedi and raja_choudhary04), and the report says so.
- **Briefs reuse only the brand's own claims**, and each claim is rated against ads for the same product
  (thin / cheaper / average / costlier), so a cheap product doesn't make its claims look good by itself.
  Claims with one ad or worse-than-average results were dropped. Expected performance comes from lookalike
  ads of the same product, and says how much of the advantage is the product rather than the format.
- **Audience data is shown, never scored**, but a red flag is surfaced: storiesbyvihaa's audience is 70% men,
  so her card says to check the audience before booking.
- **Static HTML report, not an app.** The reader needs to read and trust it, not tune it. It needs no
  server, it is rebuilt by one command, and the weights stay editable in code.

## What I'd build next with one more week

1. **A test plan, not just a ranking.** Turn the five briefs into a structured test: same product, a fixed
   budget per creator, and a pre-registered primary metric. Size it so a 30% CPA difference would be
   detectable, and report the minimum budget that needs.
2. **Telugu and Hindi head to head** with storiesbyvihaa. It is the biggest untested assumption in the answer.
3. **Watch every ad properly.** The headline label was checked on all 39 tagged ads from sampled frames,
   which left 9 "unclear". Run a vision model over all 100 MP4s at full frame rate to re-label the visual
   fields and measure its agreement with the 178 hand checks.
4. **Model ingredients jointly with partial pooling** (a hierarchical Bayesian model). It would replace the
   one-at-a-time comparisons and give the manager probability statements ("80% likely to be cheaper").
5. **Creator post-level evidence.** Score each creator's own posts that already contain the ingredients
   (a child eating, a taste reaction) on engagement, instead of using shares of posts as the proxy.
6. **A small editable view of the weights** (a sliders page) for the marketing team, backed by the same
   Python scoring.
