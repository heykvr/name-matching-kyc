# NOTES

## 1. How to run this, from a clean checkout

Needs Python 3.9+. Nothing else.

```bash
# 1. setup
python3 -m venv venv
source venv/bin/activate            # Windows: venv\Scripts\activate
pip install -r requirements.txt

# 2. generate the labeled dataset
python3 data/build_dataset.py
# writes data/name_pairs.csv (148 pairs)

# 3. run all 4 algorithms on the full dataset
python3 main_pipeline.py
# prints the metrics table below, plus a threshold sweep
# writes results/predictions.csv, results/metrics.csv,
#        results/misclassified.csv, results/threshold_sweep.csv

# 4. run the tests
pytest -q
```

No database, no network calls, no API keys.

## 2. Why this metric

The two error types aren't equally bad here:

- **False accept**: says "same person" when they're not. Lets someone impersonate an identity. This is the real security failure.
- **False reject**: says "different people" when they're the same. Sends a real customer to manual review. Annoying, but not a security failure.

Since a false accept is worse, precision should matter more than recall. Plain F1 treats them equally, so I used **F0.5** (weights precision 2x) as the main ranking metric. I also report **FAR** (false accept rate) and **FRR** (false reject rate) directly, since those are the numbers a risk team actually cares about. Accuracy is reported too but not used for ranking, since the dataset is intentionally not balanced.

## 3. Results (full 148-pair dataset)

| matcher | TP | FP | FN | TN | accuracy | precision | recall | F1 | **F0.5** | FAR | FRR |
|---|---|---|---|---|---|---|---|---|---|---|---|
| exact_normalized | 39 | 0 | 61 | 48 | 0.588 | 1.000 | 0.390 | 0.561 | 0.762 | **0.000** | 0.610 |
| token_fuzzy | 73 | 21 | 27 | 27 | 0.676 | 0.777 | 0.730 | 0.753 | 0.767 | 0.438 | 0.270 |
| phonetic | 59 | 2 | 41 | 46 | 0.709 | 0.967 | 0.590 | 0.733 | 0.858 | 0.042 | 0.410 |
| **hybrid_rule** | 96 | 7 | 4 | 41 | **0.926** | 0.932 | 0.960 | 0.946 | **0.938** | 0.146 | 0.040 |

Every prediction is in `results/predictions.csv`, so these numbers can be checked row by row, not just trusted. Wrong predictions alone are in `results/misclassified.csv`. `results/threshold_sweep.csv` shows the thresholds hard-coded in `algorithms/*.py` are close to the F0.5-optimal point, they weren't picked by eye.

## 4. Recommendation

**Ship `hybrid_rule`.** It has the best F0.5 (0.938) and accuracy (0.926), and its FAR (0.146) is far below token_fuzzy's (0.438) while still catching almost all real matches (recall 0.960).

This isn't a hedge, but there's one condition that would change it: if a false reject is actually more expensive than a false accept for Digio (e.g. manual review is costly and there's a downstream fraud check that would catch impersonation anyway), the weighting should shift toward recall, and a lower `token_fuzzy` threshold becomes worth revisiting alongside that downstream check. It still wouldn't replace `hybrid_rule` outright, since even at its most lenient setting `token_fuzzy`'s FAR is too high for KYC on its own. In production, I'd get the real cost ratio of a false accept vs a false reject from the risk team, then pick the row in `threshold_sweep.csv` that minimizes `FAR * cost_of_false_accept + FRR * cost_of_false_reject`.

## 5. The edge case I'm proudest of catching

**"Rajesh Kumar" vs "Ramesh Kumar"**, a real non-match with a common surname and a one-letter-different given name. This is the "deceptively close negative" the brief asks for, and it's the one case that breaks my best matcher: `hybrid_rule` predicts match (score 0.917) because `rapidfuzz.ratio("rajesh", "ramesh") = 83`, which clears the 80-point typo-tolerance threshold. See `tests/test_matchers.py::test_hybrid_known_weakness_rajesh_ramesh` and `results/misclassified.csv`, it's a measured failure, not a hypothetical.

A fixed edit-distance threshold can't tell "typo of the same name" apart from "different name that's one edit away." Same root cause explains 7 of the 11 remaining errors (Deepa/Deepika, Arjun/Arun, Sana/Saina, Meenal/Meena, Karan/Kiran, Sonal/Sonam, plus this one). I tried one fix: require phonetic agreement in addition to edit-distance for short tokens. Checked it against every token pair using that rule before shipping it. It fixed 6 false accepts but broke 7 currently-correct matches (Chandran Pillai/Pillay, Kondapalli/Kondapally, and others), so I didn't ship it. Proud of this one because I tested the fix against the full dataset instead of assuming it would help.

Runner-up: **"Chandrasekhara Rao Yerramsetti" vs "CHANDRASEKHARA RAO YER"**. This truncation case still fails. `hybrid_rule` has a fallback that compares two names as one concatenated string when their token counts differ (see `hybrid_match.py`), but here the truncation happens inside the last token, so the token count stays 3 vs 3 and the fallback never triggers. It fixes 4 of the 5 TRUNCATED pairs in the dataset; this is the one it doesn't.

## 6. What I cut, and what I'd build next

**Cut, given the ~2 hour scope:**
- No optimal token alignment in `hybrid_rule` (it's greedy). Fine for names with 2-4 tokens, but a real simplification.
- No nickname/alias handling (e.g. "Bunty" for a formal name). Needs a nickname dictionary I didn't have time to source for Indian names.
- No train/test split on the thresholds. I tuned against the full labeled set and reported that number directly instead of pretending I had a held-out set large enough to matter.
- Two cases came up during review that I left out on purpose, because string matching alone can't solve them: (a) two different people who happen to share the exact same legal name, there's nothing left to compare without a second identifier like DOB, and (b) single-token generic names ("Kumar" alone) that carry very little signal no matter the algorithm.

**If I had another day:**
1. Fix the Rajesh/Ramesh class of failure, the biggest remaining error category. Make the typo-tolerance rule length- and position-aware, or require phonetic and edit-distance agreement together for short tokens instead of either alone.
2. Extend the whole-string fallback to catch mid-token truncation (like Chandrasekhara/Yerramsetti above), not just cases where token counts differ.
3. Add a confidence band (auto-accept / manual-review / auto-reject) instead of a single binary threshold. The score each matcher returns already supports this; it just needs real review-queue cost data to place the cut points.
4. Build a bigger, adversarially-mined negative set. My SIBLING/COMMON_SURNAME/NEAR_DUP pairs are hand-written from general knowledge of Indian names. A production dataset should mine real near-miss pairs the system gets wrong instead.
