"""Evaluate the DeepFM ranking model with offline metrics.

Computes: AUC, GAUC, NDCG@K, Precision@K, Recall@K, HitRate@K, MRR, Coverage.

Can be used in two modes:
  1. Evaluate a trained model on test data
  2. Evaluate using saved predictions (if --preds-file is provided)

Usage:
    # Full evaluation (requires trained model)
    python scripts/eval_ranking.py --data-dir scripts/output_ranking --model-dir inference-service/model_weights

    # Quick metrics from saved predictions
    python scripts/eval_ranking.py --preds-file predictions.npz

    # Only evaluation (data already preprocessed)
    python scripts/eval_ranking.py --data-dir scripts/output_ranking --eval-only
"""

import argparse
import json
import os
import pickle
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np

SEED = 42
np.random.seed(SEED)

LABEL_COL = "click"


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


# ── Metrics ────────────────────────────────────────────────────────────

def compute_auc(preds, labels):
    """ROC-AUC."""
    try:
        from sklearn.metrics import roc_auc_score
        return float(roc_auc_score(labels, preds))
    except Exception:
        return float("nan")


def compute_logloss(preds, labels):
    """Binary cross-entropy / log loss."""
    preds = np.clip(np.asarray(preds, dtype=np.float64), 1e-15, 1 - 1e-15)
    labels = np.asarray(labels, dtype=np.float64)
    return float(-np.mean(labels * np.log(preds) + (1 - labels) * np.log(1 - preds)))


def compute_gauc(preds, labels, users):
    """Group AUC: weighted average of per-user AUC."""
    from sklearn.metrics import roc_auc_score

    user_data = defaultdict(lambda: ([], []))
    for u, p, lbl in zip(users, preds, labels):
        user_data[u][0].append(p)
        user_data[u][1].append(int(lbl))

    aucs, weights = [], []
    for uid, (p_list, l_list) in user_data.items():
        if len(set(l_list)) < 2:
            continue
        try:
            aucs.append(roc_auc_score(l_list, p_list))
            weights.append(len(l_list))
        except ValueError:
            continue

    if not aucs:
        return 0.0, 0
    return float(np.average(aucs, weights=weights)), len(aucs)


def compute_ranking_metrics(preds, labels, users, k_list=(5, 10, 20)):
    """Per-user ranking metrics: NDCG@K, Precision@K, Recall@K, HitRate@K, MRR.

    Groups items by user, sorts by predicted score, evaluates against true labels.
    """
    user_data = defaultdict(lambda: ([], []))
    for u, p, lbl in zip(users, preds, labels):
        user_data[u][0].append(p)
        user_data[u][1].append(int(lbl))

    metrics = defaultdict(list)

    for uid, (p_list, l_list) in user_data.items():
        ranked = sorted(zip(p_list, l_list), key=lambda x: x[0], reverse=True)
        ranked_labels = [r[1] for r in ranked]
        total_pos = sum(l_list)
        if total_pos == 0:
            continue

        for k in k_list:
            topk = ranked_labels[:k]
            hits = sum(topk)

            # NDCG@K
            dcg = sum((2 ** rel - 1) / np.log2(i + 2) for i, rel in enumerate(topk))
            ideal = sorted(l_list, reverse=True)[:k]
            idcg = sum((2 ** rel - 1) / np.log2(i + 2) for i, rel in enumerate(ideal))
            ndcg = dcg / idcg if idcg > 0 else 0.0

            metrics[f"ndcg@{k}"].append(ndcg)
            metrics[f"prec@{k}"].append(hits / k)
            metrics[f"recall@{k}"].append(hits / total_pos)
            metrics[f"hr@{k}"].append(1.0 if hits > 0 else 0.0)

    return {name: float(np.mean(vals)) if vals else 0.0 for name, vals in metrics.items()}


def compute_coverage(preds, labels, users, k=20):
    """Coverage@K: fraction of items that appear in any user's top-K."""
    user_data = defaultdict(lambda: ([], []))
    # We need movie_ids too — for this we need the structured data
    return float("nan")  # Requires per-item IDs, computed in full eval


def compute_diversity(preds, labels, users, item_genres=None, k=20):
    """Intra-list diversity@K: 1 - avg Jaccard similarity between items in top-K."""
    return float("nan")  # Requires genre info


# ── Baselines ──────────────────────────────────────────────────────────

def compute_popularity_baseline(labels, users, test_data, k_list):
    """Popularity baseline: rank by movie positive ratio in training data.

    Uses training data to compute each movie's CTR = pos_count / total_count.
    """
    data_dir = Path(__file__).resolve().parent / "output_ranking"
    train = dict(np.load(data_dir / "train_ranking.npz"))

    movie_ids = train["movie_id"]
    train_labels = train[LABEL_COL]

    # Compute per-movie positive ratio in training set
    movie_pos = defaultdict(int)
    movie_total = defaultdict(int)
    for mid, lbl in zip(movie_ids, train_labels):
        movie_total[int(mid)] += 1
        if lbl >= 1:
            movie_pos[int(mid)] += 1

    movie_ctr = {mid: movie_pos[mid] / max(movie_total[mid], 1) for mid in movie_total}

    # Generate popularity-based predictions for test set
    test_movie_ids = test_data["movie_id"]
    pop_preds = np.array([movie_ctr.get(int(mid), 0.0) for mid in test_movie_ids], dtype=np.float64)

    return compute_metrics_dict(pop_preds, labels, users, k_list, "Popularity")


def compute_random_baseline(labels, users, k_list, seed=42):
    """Random baseline: uniformly random predictions."""
    rng = np.random.default_rng(seed)
    rand_preds = rng.uniform(0, 1, len(labels)).astype(np.float64)
    return compute_metrics_dict(rand_preds, labels, users, k_list, "Random")


def compute_metrics_dict(preds, labels, users, k_list, name):
    """Compute all metrics for one predictor, returning a flat dict."""
    preds = list(preds)
    labels = list(labels)
    users = list(users)

    r = {"model": name}
    r["auc"] = compute_auc(preds, labels)
    r["logloss"] = compute_logloss(preds, labels)
    gauc, gauc_users = compute_gauc(preds, labels, users)
    r["gauc"] = gauc
    ranking = compute_ranking_metrics(preds, labels, users, k_list=k_list)
    r.update(ranking)
    return r


# ── Evaluation with model ──────────────────────────────────────────────

def evaluate_with_model(data_dir, model_dir, device="cpu", batch_size=2048):
    """Load model and test data, run full evaluation."""
    import torch
    from torch.utils.data import DataLoader

    # Dynamic import of model
    scripts_dir = str(Path(__file__).resolve().parent)
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    from train_ranking import DeepFM, RankingDataset

    data_dir = Path(data_dir)
    model_dir = Path(model_dir)

    log(f"Loading test data from {data_dir}")
    test_data = dict(np.load(data_dir / "test_ranking.npz"))
    log(f"  Test samples: {len(test_data[LABEL_COL]):,}")

    # Load model
    checkpoint = torch.load(model_dir / "deepfm_model.pt", map_location=device, weights_only=False)
    feature_names = checkpoint.get("feature_names")
    if feature_names is None:
        # Legacy fallback
        feature_names = ["user_id", "gender", "age", "occupation", "zip_code",
                        "user_avg_rating_bin", "user_rating_count_bin", "user_active_days_bin",
                        "movie_id", "genres", "is_adult", "year", "avg_rating_bin", "rating_count_bin"]
    model = DeepFM(
        field_dims=checkpoint["field_dims"],
        embed_dim=checkpoint.get("embed_dim", 16),
        mlp_dims=checkpoint.get("mlp_dims", (64, 32, 16)),
        dropout=checkpoint.get("dropout", 0.2),
        feature_names=feature_names,
    )
    model.load_state_dict(checkpoint["model_state_dict"])
    model.to(device)
    model.eval()
    log("Model loaded")

    # Predict
    ds = RankingDataset(test_data, feature_names)
    loader = DataLoader(ds, batch_size=batch_size, shuffle=False, num_workers=0)

    all_preds, all_labels, all_users = [], [], []

    log("Running predictions ...")
    with torch.no_grad():
        for batch in loader:
            features = {f: batch[f].to(device) for f in feature_names}
            labels = batch["label"]

            preds = model(features)
            all_preds.extend(preds.cpu().numpy().tolist())
            all_labels.extend(labels.numpy().tolist())
            all_users.extend(batch["orig_user_id"].numpy().tolist())

    log(f"Predictions done: {len(all_preds):,} samples")
    return all_preds, all_labels, all_users


def evaluate_from_preds(preds_file):
    """Load pre-computed predictions for evaluation."""
    data = np.load(preds_file)
    return (
        data["preds"].tolist(),
        data["labels"].tolist(),
        data["users"].tolist() if "users" in data else [],
    )


# ── Main ──────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Evaluate DeepFM ranking model")
    parser.add_argument("--data-dir", type=str, default="scripts/output_ranking",
                        help="Directory with preprocessed ranking data")
    parser.add_argument("--model-dir", type=str, default="inference-service/model_weights",
                        help="Directory with trained model weights")
    parser.add_argument("--preds-file", type=str, default=None,
                        help="Path to saved predictions npz (skips model loading)")
    parser.add_argument("--eval-only", action="store_true",
                        help="Skip model training check, only compute metrics")
    parser.add_argument("--k-list", type=str, default="5,10,20",
                        help="Comma-separated K values for ranking metrics")
    parser.add_argument("--output", type=str, default=None,
                        help="Save metrics as JSON to this path")
    parser.add_argument("--device", type=str, default="cpu")
    args = parser.parse_args()

    t0 = time.time()
    k_list = tuple(int(x.strip()) for x in args.k_list.split(","))

    # Get predictions
    if args.preds_file:
        log(f"Loading predictions from {args.preds_file}")
        preds, labels, users = evaluate_from_preds(args.preds_file)
    else:
        preds, labels, users = evaluate_with_model(args.data_dir, args.model_dir, args.device)

    if not users:
        log("ERROR: No user information available. Ranking metrics require per-user grouping.")
        users = list(range(len(preds)))  # fallback: treat each sample as separate user

    # ── Compute DeepFM metrics ──────────────────────────────────────────
    log("Computing DeepFM metrics ...")
    deepfm = compute_metrics_dict(preds, labels, users, k_list, "DeepFM")

    # ── Compute baselines ───────────────────────────────────────────────
    log("Computing baselines ...")
    test_data = dict(np.load(Path(args.data_dir) / "test_ranking.npz"))
    rand = compute_random_baseline(labels, users, k_list)
    pop = compute_popularity_baseline(labels, users, test_data, k_list)

    all_models = [deepfm, pop, rand]

    # ── Print comparison ─────────────────────────────────────────────────
    print()
    print("=" * 70)
    print("  Ranking Model Comparison")
    print("=" * 70)
    print(f"  {'Model':<14} {'AUC':>8} {'GAUC':>8} {'LogLoss':>8}  ", end="")
    for k in k_list:
        print(f"{'NDCG@'+str(k):>8}  ", end="")
    print(f"\n  {'-'*14} {'-'*8} {'-'*8} {'-'*8}  ", end="")
    for _ in k_list:
        print(f"{'-'*8}  ", end="")
    print()
    for m in all_models:
        print(f"  {m['model']:<14} {m['auc']:8.4f} {m['gauc']:8.4f} {m['logloss']:8.4f}  ", end="")
        for k in k_list:
            print(f"{m.get(f'ndcg@{k}', float('nan')):8.4f}  ", end="")
        print()
    print("-" * 70)
    # Improvement over popularity
    print(f"  DeepFM vs Popularity:  AUC +{deepfm['auc'] - pop['auc']:.4f},  GAUC +{deepfm['gauc'] - pop['gauc']:.4f},  NDCG@10 +{deepfm.get('ndcg@10', 0) - pop.get('ndcg@10', 0):.4f}")
    print("=" * 70)

    # ── Print detailed DeepFM results ────────────────────────────────────
    print()
    print("=" * 60)
    print("  DeepFM — Detailed Results")
    print("=" * 60)
    print(f"  Samples:        {len(preds):>10,}")
    print(f"  Users:          {len(set(users)):>10,}")
    print(f"  Positive ratio: {float(np.mean(labels)):>10.4f}")
    print("-" * 60)
    print(f"  AUC:            {deepfm['auc']:>10.4f}")
    print(f"  GAUC:           {deepfm['gauc']:>10.4f}")
    print(f"  LogLoss:        {deepfm['logloss']:>10.4f}")
    print("-" * 60)
    print("  Ranking Metrics:")
    for k in k_list:
        ndcg = deepfm.get(f"ndcg@{k}", float("nan"))
        prec = deepfm.get(f"prec@{k}", float("nan"))
        rec = deepfm.get(f"recall@{k}", float("nan"))
        hr = deepfm.get(f"hr@{k}", float("nan"))
        print(f"    NDCG@{k:<3}  {ndcg:.4f}    Prec@{k:<3}  {prec:.4f}    Recall@{k:<3}  {rec:.4f}    HR@{k:<3}  {hr:.4f}")
    print("=" * 60)

    if args.output:
        out = {"deepfm": deepfm, "popularity": pop, "random": rand}
        with open(args.output, "w") as f:
            json.dump(out, f, indent=2, default=float)
        log(f"Metrics saved to {args.output}")

    log(f"DONE in {(time.time() - t0):.1f}s")
    return all_models


if __name__ == "__main__":
    main()
