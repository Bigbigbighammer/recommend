"""Train BPR matrix-factorization recall artifacts.

This is a lightweight learning-to-rank recall model. It learns user and item
embeddings with Bayesian Personalized Ranking and exports NumPy artifacts for
the Java online recall layer:

  - bpr_user_emb.npy
  - bpr_user_ids.npy
  - bpr_item_emb.npy
  - bpr_movie_ids.npy
  - bpr_meta.json
"""

from __future__ import annotations

import argparse
import json
import random
import time
from pathlib import Path

import numpy as np
import pandas as pd

from offline_recall_eval import (
    evaluate,
    load_pickle,
    normalize_columns,
    resolve_data_dir,
    split_by_time,
)


def normalize_rows(matrix: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    return matrix / np.where(norms == 0.0, 1.0, norms)


def positive_threshold(ratings: pd.DataFrame, value: str) -> float:
    if value == "auto":
        return 4.0 if ratings["rating"].max() <= 5 else 8.0
    return float(value)


def build_full_histories(ratings: pd.DataFrame, min_rating: float) -> dict[int, list[int]]:
    positives = ratings[ratings["rating"] >= min_rating].sort_values(["user_id", "timestamp"])
    return {
        int(user_id): [int(v) for v in group["movie_id"].tolist()]
        for user_id, group in positives.groupby("user_id")
        if len(group) >= 1
    }


def build_mappings(histories: dict[int, list[int]], movie_ids_all: list[int]):
    user_ids = np.array(sorted(histories), dtype=np.int64)
    movie_ids = np.array(sorted(set(movie_ids_all) | {item for items in histories.values() for item in items}), dtype=np.int64)
    user_to_idx = {int(user_id): idx for idx, user_id in enumerate(user_ids.tolist())}
    movie_to_idx = {int(movie_id): idx for idx, movie_id in enumerate(movie_ids.tolist())}
    positives = {
        user_to_idx[user_id]: {movie_to_idx[item] for item in items if item in movie_to_idx}
        for user_id, items in histories.items()
    }
    return user_ids, movie_ids, user_to_idx, movie_to_idx, positives


def train_bpr(
    histories: dict[int, list[int]],
    movie_ids_all: list[int],
    dim: int,
    epochs: int,
    lr: float,
    reg: float,
    max_samples: int,
    seed: int,
):
    user_ids, movie_ids, user_to_idx, movie_to_idx, positives = build_mappings(histories, movie_ids_all)
    rng = np.random.default_rng(seed)
    user_emb = rng.normal(0.0, 0.1, (len(user_ids), dim)).astype(np.float64)
    item_emb = rng.normal(0.0, 0.1, (len(movie_ids), dim)).astype(np.float64)
    users = list(positives)
    item_count = len(movie_ids)
    samples_per_epoch = max_samples if max_samples > 0 else sum(len(v) for v in positives.values())

    print(f"Users: {len(user_ids):,}, items: {len(movie_ids):,}, dim={dim}")
    print(f"BPR samples per epoch: {samples_per_epoch:,}")
    for epoch in range(1, epochs + 1):
        started = time.time()
        loss_sum = 0.0
        for step in range(1, samples_per_epoch + 1):
            u = int(rng.choice(users))
            pos_items = positives[u]
            if not pos_items:
                continue
            i = int(rng.choice(list(pos_items)))
            j = int(rng.integers(0, item_count))
            while j in pos_items:
                j = int(rng.integers(0, item_count))

            u_vec = user_emb[u].copy()
            i_vec = item_emb[i].copy()
            j_vec = item_emb[j].copy()
            x = float(u_vec @ (i_vec - j_vec))
            grad = 1.0 / (1.0 + np.exp(np.clip(x, -30.0, 30.0)))
            loss_sum += float(np.log1p(np.exp(-np.clip(x, -30.0, 30.0))))

            user_emb[u] += lr * (grad * (i_vec - j_vec) - reg * u_vec)
            item_emb[i] += lr * (grad * u_vec - reg * i_vec)
            item_emb[j] += lr * (-grad * u_vec - reg * j_vec)

            if step % 200000 == 0:
                print(f"  epoch {epoch}/{epochs} step {step:,}/{samples_per_epoch:,} loss={loss_sum / step:.4f}")
        print(f"Epoch {epoch} done in {(time.time() - started):.1f}s, loss={loss_sum / samples_per_epoch:.4f}")

    return user_ids, movie_ids, normalize_rows(user_emb), normalize_rows(item_emb)


def bpr_recall(user_id: int, history: list[int], user_to_idx, movie_ids, movie_to_idx, user_emb, item_emb, topk: int):
    if user_id not in user_to_idx:
        return []
    seen = set(history)
    scores = item_emb @ user_emb[user_to_idx[user_id]]
    ranked = np.argpartition(-scores, min(len(scores) - 1, topk * 3))[: topk * 3]
    ranked = ranked[np.argsort(-scores[ranked])]
    recs = []
    for idx in ranked:
        movie_id = int(movie_ids[idx])
        if movie_id not in seen:
            recs.append(movie_id)
            if len(recs) >= topk:
                break
    return recs


def evaluate_bpr(train_by_user, test_by_user, user_ids, movie_ids, user_emb, item_emb, output: str):
    user_to_idx = {int(user_id): idx for idx, user_id in enumerate(user_ids.tolist())}
    movie_to_idx = {int(movie_id): idx for idx, movie_id in enumerate(movie_ids.tolist())}
    recs = {
        user_id: bpr_recall(user_id, history, user_to_idx, movie_ids, movie_to_idx, user_emb, item_emb, 300)
        for user_id, history in train_by_user.items()
    }
    result = pd.DataFrame(evaluate("bpr", recs, test_by_user, [20, 50, 100]))
    print()
    print("BPR evaluation:")
    print(result.round(4))
    if output:
        path = Path(output)
        path.parent.mkdir(parents=True, exist_ok=True)
        result.to_csv(path, index=False, encoding="utf-8-sig")
        print(f"Saved BPR metrics to {path}")


def save_artifacts(out_dir: Path, user_ids, movie_ids, user_emb, item_emb, meta) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    np.save(out_dir / "bpr_user_ids.npy", user_ids.astype(np.int64))
    np.save(out_dir / "bpr_movie_ids.npy", movie_ids.astype(np.int64))
    np.save(out_dir / "bpr_user_emb.npy", user_emb.astype(np.float64))
    np.save(out_dir / "bpr_item_emb.npy", item_emb.astype(np.float64))
    with (out_dir / "bpr_meta.json").open("w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    print(f"Wrote BPR artifacts to {out_dir}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", default="scripts/data")
    parser.add_argument("--out-dir", default="data")
    parser.add_argument("--min-rating", default="auto")
    parser.add_argument("--dim", type=int, default=48)
    parser.add_argument("--epochs", type=int, default=4)
    parser.add_argument("--lr", type=float, default=0.035)
    parser.add_argument("--reg", type=float, default=0.002)
    parser.add_argument("--max-samples", type=int, default=700000)
    parser.add_argument("--test-ratio", type=float, default=0.2)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--eval-output", default="test-results/bpr_eval.csv")
    parser.add_argument("--skip-eval", action="store_true")
    args = parser.parse_args()

    random.seed(args.seed)
    data_dir = resolve_data_dir(args.data_dir)
    ratings = normalize_columns(load_pickle(data_dir / "ratings.pkl"))
    movies = normalize_columns(load_pickle(data_dir / "movies.pkl"))
    if "timestamp" not in ratings.columns:
        ratings["timestamp"] = ratings.groupby("user_id").cumcount()
    ratings["user_id"] = ratings["user_id"].astype(int)
    ratings["movie_id"] = ratings["movie_id"].astype(int)
    ratings["rating"] = ratings["rating"].astype(float)
    movies["movie_id"] = movies["movie_id"].astype(int)
    movie_ids_all = [int(v) for v in movies["movie_id"].tolist()]
    min_rating = positive_threshold(ratings, args.min_rating)

    print(f"Data dir: {data_dir}")
    print(f"Positive threshold rating >= {min_rating}")
    if not args.skip_eval:
        print("Training evaluation BPR model on time-based train split...")
        _, train_by_user, _, test_by_user = split_by_time(ratings, args.test_ratio, min_rating, 0.0)
        user_ids, movie_ids, user_emb, item_emb = train_bpr(
            train_by_user, movie_ids_all, args.dim, args.epochs, args.lr, args.reg, args.max_samples, args.seed)
        evaluate_bpr(train_by_user, test_by_user, user_ids, movie_ids, user_emb, item_emb, args.eval_output)

    print()
    print("Training final online BPR model on all positive histories...")
    histories = build_full_histories(ratings, min_rating)
    user_ids, movie_ids, user_emb, item_emb = train_bpr(
        histories, movie_ids_all, args.dim, args.epochs, args.lr, args.reg, args.max_samples, args.seed)
    meta = {
        "version": "bpr-mf-v1",
        "trained_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "positive_threshold": float(min_rating),
        "dim": args.dim,
        "epochs": args.epochs,
        "max_samples": args.max_samples,
        "lr": args.lr,
        "reg": args.reg,
        "seed": args.seed,
    }
    save_artifacts(Path(args.out_dir), user_ids, movie_ids, user_emb, item_emb, meta)


if __name__ == "__main__":
    main()
