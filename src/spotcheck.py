"""Label agreement rates from the hand spot-check in annotations/label_spotcheck.csv.

Sample: 20 ads drawn with pandas .sample(20, random_state=2026) for transcript checks
(outputs/spotcheck_sample_ids.csv), plus 10 ads checked against video frames (0.3s, 1.5s, 2.8s and
three later points), chosen because their key child labels could not be verified from the transcript.
Rows marked n/a could not be judged and are excluded from the rate.

Run:  python src/spotcheck.py
"""
import numpy as np
import pandas as pd

import metrics as m

ANN = m.ROOT / "annotations" / "label_spotcheck.csv"


def wilson(k, n, z=1.96):
    """95% Wilson interval for a proportion (well-behaved at small n and near 100%)."""
    if n == 0:
        return np.nan, np.nan
    p = k / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return centre - half, centre + half


def agreement() -> pd.DataFrame:
    ann = pd.read_csv(ANN, keep_default_na=False)  # keep the literal "n/a" marker
    judged = ann[ann.agree != "n/a"]
    rows = []
    for label, g in judged.groupby("label", sort=False):
        k, n = int((g.agree == "yes").sum()), len(g)
        lo, hi = wilson(k, n)
        rows.append({"label": label, "agree": k, "checked": n, "rate": k / n, "lo95": lo, "hi95": hi,
                     "not_judgeable": int((ann.label == label).sum() - n),
                     "disagreements": "; ".join(f"{r.ad_id}: {r.note}" for r in g[g.agree == "no"].itertuples())})
    out = pd.DataFrame(rows)
    k, n = int((judged.agree == "yes").sum()), len(judged)
    lo, hi = wilson(k, n)
    out.loc[len(out)] = {"label": "ALL", "agree": k, "checked": n, "rate": k / n, "lo95": lo, "hi95": hi,
                         "not_judgeable": int((ann.agree == "n/a").sum()), "disagreements": ""}
    return out


if __name__ == "__main__":
    pd.set_option("display.width", 250)
    res = agreement()
    res.to_csv(m.OUT / "phase1_label_agreement.csv", index=False)
    print(res.round(2).to_string(index=False, max_colwidth=110))
