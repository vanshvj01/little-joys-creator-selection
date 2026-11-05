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

**User decisions:** _(pending)_
