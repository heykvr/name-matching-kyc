"""
main_pipeline.py - the single entry point that orchestrates everything:
loads the dataset, runs every algorithm in algorithms/ against it, computes
metrics, and writes verifiable results to results/.

Usage:
    python3 main_pipeline.py
"""
import csv
import os

from algorithms import get_all_matchers
from algorithms.fuzzy_match import TokenFuzzyMatcher
from algorithms.phonetic_match import PhoneticMatcher
from algorithms.hybrid_match import HybridRuleMatcher

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(ROOT, "data", "name_pairs.csv")
RESULTS_DIR = os.path.join(ROOT, "results")


def load_dataset(path=DATA_PATH):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def confusion_matrix(rows, predictions):
    tp = fp = fn = tn = 0
    for row, pred in zip(rows, predictions):
        actual = row["label"] == "match"
        if pred and actual:
            tp += 1
        elif pred and not actual:
            fp += 1
        elif not pred and actual:
            fn += 1
        else:
            tn += 1
    return tp, fp, fn, tn


def metrics_from_confusion(tp, fp, fn, tn):
    total = tp + fp + fn + tn
    accuracy = (tp + tn) / total if total else 0.0
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    # F0.5 weights precision (avoiding false accepts) twice as heavily as
    # recall -- see NOTES.md for why that asymmetry is correct for identity
    # verification specifically.
    beta = 0.5
    f0_5 = (
        (1 + beta**2) * precision * recall / (beta**2 * precision + recall)
        if (beta**2 * precision + recall)
        else 0.0
    )
    false_accept_rate = fp / (fp + tn) if (fp + tn) else 0.0   # wrongly says "same person"
    false_reject_rate = fn / (fn + tp) if (fn + tp) else 0.0   # wrongly says "different person"
    return {
        "accuracy": accuracy, "precision": precision, "recall": recall,
        "f1": f1, "f0.5": f0_5,
        "false_accept_rate": false_accept_rate, "false_reject_rate": false_reject_rate,
    }


def run_full_evaluation(verbose=True):
    rows = load_dataset()
    matchers = get_all_matchers()
    os.makedirs(RESULTS_DIR, exist_ok=True)

    per_pair_path = os.path.join(RESULTS_DIR, "predictions.csv")
    matcher_predictions = {m.name: [] for m in matchers}
    matcher_scores = {m.name: [] for m in matchers}

    with open(per_pair_path, "w", newline="", encoding="utf-8") as f:
        fieldnames = ["pair_id", "name_a", "name_b", "label", "category"]
        for m in matchers:
            fieldnames += [f"{m.name}_pred", f"{m.name}_score", f"{m.name}_correct"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            out = {k: row[k] for k in ["pair_id", "name_a", "name_b", "label", "category"]}
            actual = row["label"] == "match"
            for m in matchers:
                result = m.match(row["name_a"], row["name_b"])
                matcher_predictions[m.name].append(result.is_match)
                matcher_scores[m.name].append(result.score)
                out[f"{m.name}_pred"] = "match" if result.is_match else "non_match"
                out[f"{m.name}_score"] = round(result.score, 3)
                out[f"{m.name}_correct"] = result.is_match == actual
            writer.writerow(out)

    metrics_path = os.path.join(RESULTS_DIR, "metrics.csv")
    all_metrics = {}
    with open(metrics_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["matcher", "tp", "fp", "fn", "tn", "accuracy", "precision", "recall", "f1", "f0.5",
                          "false_accept_rate", "false_reject_rate"])
        for m in matchers:
            tp, fp, fn, tn = confusion_matrix(rows, matcher_predictions[m.name])
            met = metrics_from_confusion(tp, fp, fn, tn)
            all_metrics[m.name] = {"confusion": (tp, fp, fn, tn), **met}
            writer.writerow([m.name, tp, fp, fn, tn] + [round(met[k], 4) for k in
                             ["accuracy", "precision", "recall", "f1", "f0.5", "false_accept_rate", "false_reject_rate"]])

    if verbose:
        print(f"\nLoaded {len(rows)} labeled pairs from {DATA_PATH}\n")
        header = f"{'matcher':<18}{'TP':>4}{'FP':>4}{'FN':>4}{'TN':>4}{'acc':>8}{'prec':>8}{'recall':>8}{'F1':>8}{'F0.5':>8}{'FAR':>8}{'FRR':>8}"
        print(header)
        print("-" * len(header))
        for m in matchers:
            tp, fp, fn, tn = all_metrics[m.name]["confusion"]
            met = all_metrics[m.name]
            print(f"{m.name:<18}{tp:>4}{fp:>4}{fn:>4}{tn:>4}"
                  f"{met['accuracy']:>8.3f}{met['precision']:>8.3f}{met['recall']:>8.3f}"
                  f"{met['f1']:>8.3f}{met['f0.5']:>8.3f}{met['false_accept_rate']:>8.3f}{met['false_reject_rate']:>8.3f}")
        print(f"\nFAR = false accept rate (says match, actually different people -- the costly error in KYC)")
        print(f"FRR = false reject rate (says non-match, actually same person -- causes manual-review friction)")
        print(f"\nFull per-pair predictions written to {per_pair_path}")
        print(f"Metrics table written to {metrics_path}")

    misclass_path = os.path.join(RESULTS_DIR, "misclassified.csv")
    with open(misclass_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["matcher", "pair_id", "name_a", "name_b", "label", "category", "predicted", "score"])
        for m in matchers:
            for row, pred, score in zip(rows, matcher_predictions[m.name], matcher_scores[m.name]):
                actual = row["label"] == "match"
                if pred != actual:
                    writer.writerow([m.name, row["pair_id"], row["name_a"], row["name_b"],
                                      row["label"], row["category"], "match" if pred else "non_match", round(score, 3)])
    if verbose:
        print(f"Misclassified pairs (for qualitative review) written to {misclass_path}\n")

    return all_metrics, rows, matcher_predictions, matcher_scores


def threshold_sweep(verbose=True):
    """Sweep thresholds for the three score-based matchers to justify the
    hard-coded defaults in algorithms/*.py, rather than asserting they're right."""
    rows = load_dataset()
    sweep_path = os.path.join(RESULTS_DIR, "threshold_sweep.csv")
    os.makedirs(RESULTS_DIR, exist_ok=True)

    configs = [
        ("token_fuzzy", TokenFuzzyMatcher, [70, 75, 78, 80, 82, 85, 88, 90, 92, 95]),
        ("phonetic", PhoneticMatcher, [0.5, 0.6, 0.7, 0.75, 0.8, 0.85, 0.9, 1.0]),
        ("hybrid_rule", HybridRuleMatcher, [0.55, 0.60, 0.65, 0.70, 0.75, 0.80, 0.85, 0.90]),
    ]

    with open(sweep_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["matcher", "threshold", "tp", "fp", "fn", "tn", "precision", "recall", "f0.5", "false_accept_rate"])
        for name, cls, thresholds in configs:
            if verbose:
                print(f"\nThreshold sweep: {name}")
                print(f"{'threshold':>10}{'TP':>5}{'FP':>5}{'FN':>5}{'TN':>5}{'prec':>8}{'recall':>8}{'F0.5':>8}{'FAR':>8}")
            for t in thresholds:
                kwargs = {"threshold": t} if name != "phonetic" else {"overlap_threshold": t}
                matcher = cls(**kwargs)
                preds = [matcher.match(r["name_a"], r["name_b"]).is_match for r in rows]
                tp, fp, fn, tn = confusion_matrix(rows, preds)
                met = metrics_from_confusion(tp, fp, fn, tn)
                writer.writerow([name, t, tp, fp, fn, tn, round(met["precision"], 4), round(met["recall"], 4),
                                  round(met["f0.5"], 4), round(met["false_accept_rate"], 4)])
                if verbose:
                    print(f"{t:>10}{tp:>5}{fp:>5}{fn:>5}{tn:>5}"
                          f"{met['precision']:>8.3f}{met['recall']:>8.3f}{met['f0.5']:>8.3f}{met['false_accept_rate']:>8.3f}")
    if verbose:
        print(f"\nFull sweep written to {sweep_path}\n")


if __name__ == "__main__":
    run_full_evaluation()
    threshold_sweep()
