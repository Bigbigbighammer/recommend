"""Train a lightweight YouTubeDNN-style two-tower recall model.

The implementation intentionally uses only NumPy so it can run in the same
course environment as the rest of the project. It trains item/user-tower
embeddings from positive user histories with sampled-softmax style negative
sampling:

  user tower: weighted pooling over historical item embeddings
  item tower: item embedding matrix used by Java ItemEmbeddingStore

Outputs under data/ by default:
  - item_emb.npy               item tower vectors loaded by Java
  - movie_ids.npy              row-to-movie-id mapping
  - youtube_user_item_emb.npy  user-tower history pooling vectors
  - youtubednn_meta.json       training metadata
"""

from __future__ import annotations

import argparse
import json
import math
import random
import time
from collections import Counter
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


def sigmoid(values: np.ndarray) -> np.ndarray:
    values = np.clip(values, -30.0, 30.0)
    return 1.0 / (1.0 + np.exp(-values))


def normalize_rows(matrix: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    return matrix / np.where(norms == 0.0, 1.0, norms)


def positive_threshold(ratings: pd.DataFrame, value: str) -> float:
    if value == "auto":
        return 4.0 if ratings["rating"].max() <= 5 else 8.0
    return float(value)


def build_histories(ratings: pd.DataFrame, min_rating: float) -> dict[int, list[int]]:
    positives = ratings[ratings["rating"] >= min_rating].sort_values(["user_id", "timestamp"])
    return {
        int(user_id): [int(v) for v in group["movie_id"].tolist()]
        for user_id, group in positives.groupby("user_id")
        if len(group) >= 2
    }


def build_vocab(movies: pd.DataFrame, histories: dict[int, list[int]]) -> tuple[np.ndarray, dict[int, int]]:
    ids = set(int(v) for v in movies["movie_id"].tolist())
    for items in histories.values():
        ids.update(items)
    movie_ids = np.array(sorted(ids), dtype=np.int64)
    movie_to_idx = {int(movie_id): idx for idx, movie_id in enumerate(movie_ids.tolist())}
    return movie_ids, movie_to_idx


def histories_to_sequences(
    histories: dict[int, list[int]],
    movie_to_idx: dict[int, int],
    history_cap: int,
) -> list[list[int]]:
    sequences: list[list[int]] = []
    for items in histories.values():
        seq = [movie_to_idx[i] for i in items[-history_cap:] if i in movie_to_idx]
        seq = list(dict.fromkeys(seq))
        if len(seq) >= 2:
            sequences.append(seq)
    return sequences


def build_pairs(sequences: list[list[int]], max_samples: int, seed: int) -> list[tuple[int, int]]:
    pairs = [(seq_idx, pos) for seq_idx, seq in enumerate(sequences) for pos in range(1, len(seq))]
    if max_samples > 0 and len(pairs) > max_samples:
        rng = random.Random(seed)
        pairs = rng.sample(pairs, max_samples)
    return pairs


def build_negative_sampler(sequences: list[list[int]], item_count: int) -> np.ndarray:
    counts = np.ones(item_count, dtype=np.float64)
    for seq in sequences:
        for item_idx in seq:
            counts[item_idx] += 1.0
    probs = np.power(counts, 0.75)
    probs /= probs.sum()
    return np.cumsum(probs)


def sample_negatives(cdf: np.ndarray, rng: np.random.Generator, size: int, positive: int) -> np.ndarray:
    negatives = np.searchsorted(cdf, rng.random(size), side="right")
    if size > 0:
        mask = negatives == positive
        while mask.any():
            negatives[mask] = np.searchsorted(cdf, rng.random(mask.sum()), side="right")
            mask = negatives == positive
    return negatives.astype(np.int64)


def train_two_tower(
    histories: dict[int, list[int]],
    movies: pd.DataFrame,
    dim: int,
    epochs: int,
    lr: float,
    negatives: int,
    history_window: int,
    history_cap: int,
    max_samples: int,
    seed: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, dict[str, int | float]]:
    movie_ids, movie_to_idx = build_vocab(movies, histories)
    sequences = histories_to_sequences(histories, movie_to_idx, history_cap)
    pairs = build_pairs(sequences, max_samples, seed)
    item_count = len(movie_ids)
    if not pairs:
        raise RuntimeError("No training pairs generated. Check min_rating and input data.")

    rng = np.random.default_rng(seed)
    user_item_emb = rng.normal(0.0, 1.0 / math.sqrt(dim), (item_count, dim)).astype(np.float64)
    item_emb = rng.normal(0.0, 1.0 / math.sqrt(dim), (item_count, dim)).astype(np.float64)
    cdf = build_negative_sampler(sequences, item_count)

    print(f"Training pairs: {len(pairs):,}")
    print(f"Items: {item_count:,}, sequences: {len(sequences):,}, dim={dim}")
    for epoch in range(1, epochs + 1):
        rng.shuffle(pairs)
        total_loss = 0.0
        started = time.time()
        for step, (seq_idx, pos) in enumerate(pairs, start=1):
            seq = sequences[seq_idx]
            target = seq[pos]
            context = seq[max(0, pos - history_window):pos]
            if not context:
                continue

            context_arr = np.array(context, dtype=np.int64)
            user_vec = user_item_emb[context_arr].mean(axis=0)

            neg_ids = sample_negatives(cdf, rng, negatives, target)
            candidate_ids = np.concatenate(([target], neg_ids))
            labels = np.zeros(1 + negatives, dtype=np.float64)
            labels[0] = 1.0

            candidate_vecs = item_emb[candidate_ids].copy()
            logits = candidate_vecs @ user_vec
            preds = sigmoid(logits)
            grad = preds - labels
            loss = -np.mean(labels * np.log(preds + 1e-12) + (1.0 - labels) * np.log(1.0 - preds + 1e-12))
            total_loss += float(loss)

            grad_user = grad @ candidate_vecs
            grad_items = grad[:, None] * user_vec[None, :]
            np.add.at(item_emb, candidate_ids, -lr * grad_items)
            np.add.at(user_item_emb, context_arr, -lr * grad_user / len(context_arr))

            if step % 100000 == 0:
                print(
                    f"  epoch {epoch}/{epochs} step {step:,}/{len(pairs):,} "
                    f"loss={total_loss / step:.4f}"
                )
        print(f"Epoch {epoch} done in {(time.time() - started):.1f}s, loss={total_loss / len(pairs):.4f}")

    item_emb = normalize_rows(item_emb)
    user_item_emb = normalize_rows(user_item_emb)
    meta = {
        "item_count": int(item_count),
        "sequence_count": int(len(sequences)),
        "pair_count": int(len(pairs)),
        "dim": int(dim),
        "epochs": int(epochs),
        "negatives": int(negatives),
        "history_window": int(history_window),
        "history_cap": int(history_cap),
        "max_samples": int(max_samples),
        "seed": int(seed),
    }
    return movie_ids, item_emb, user_item_emb, meta


def youtube_recall(
    history: list[int],
    movie_to_idx: dict[int, int],
    movie_ids: np.ndarray,
    item_emb: np.ndarray,
    user_item_emb: np.ndarray,
    topk: int,
    history_window: int,
) -> list[int]:
    seen = set(history)
    hist_idx = [movie_to_idx[i] for i in history[-history_window:] if i in movie_to_idx]
    if not hist_idx:
        return []
    weights = np.linspace(0.6, 1.0, num=len(hist_idx), dtype=np.float64)
    user_vec = np.average(user_item_emb[hist_idx], axis=0, weights=weights)
    norm = np.linalg.norm(user_vec)
    if norm == 0.0:
        return []
    user_vec = user_vec / norm
    scores = item_emb @ user_vec
    if len(scores) <= topk:
        ranked = np.argsort(-scores)
    else:
        top_idx = np.argpartition(-scores, topk)[:topk * 3]
        ranked = top_idx[np.argsort(-scores[top_idx])]
    recs = []
    for idx in ranked:
        movie_id = int(movie_ids[idx])
        if movie_id not in seen:
            recs.append(movie_id)
            if len(recs) >= topk:
                break
    return recs


def evaluate_youtube(
    train_by_user: dict[int, list[int]],
    test_by_user: dict[int, set[int]],
    movie_ids: np.ndarray,
    item_emb: np.ndarray,
    user_item_emb: np.ndarray,
    history_window: int,
    output: str,
) -> pd.DataFrame:
    movie_to_idx = {int(movie_id): idx for idx, movie_id in enumerate(movie_ids.tolist())}
    recs = {}
    for user_id, history in train_by_user.items():
        recs[user_id] = youtube_recall(
            history, movie_to_idx, movie_ids, item_emb, user_item_emb, 300, history_window)
    rows = evaluate("youtubednn", recs, test_by_user, [20, 50, 100])
    result = pd.DataFrame(rows)
    print()
    print("YouTubeDNN evaluation:")
    print(result.round(4))
    if output:
        path = Path(output)
        path.parent.mkdir(parents=True, exist_ok=True)
        result.to_csv(path, index=False, encoding="utf-8-sig")
        print(f"Saved YouTubeDNN metrics to {path}")
    return result


def save_model(
    out_dir: Path,
    movie_ids: np.ndarray,
    item_emb: np.ndarray,
    user_item_emb: np.ndarray,
    meta: dict[str, int | float | str],
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    np.save(out_dir / "item_emb.npy", item_emb.astype(np.float64))
    np.save(out_dir / "movie_ids.npy", movie_ids.astype(np.int64))
    np.save(out_dir / "youtube_user_item_emb.npy", user_item_emb.astype(np.float64))
    with (out_dir / "youtubednn_meta.json").open("w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    print(f"Wrote {out_dir / 'item_emb.npy'}")
    print(f"Wrote {out_dir / 'movie_ids.npy'}")
    print(f"Wrote {out_dir / 'youtube_user_item_emb.npy'}")
    print(f"Wrote {out_dir / 'youtubednn_meta.json'}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", default="scripts/data")
    parser.add_argument("--out-dir", default="data")
    parser.add_argument("--min-rating", default="auto")
    parser.add_argument("--dim", type=int, default=32)
    parser.add_argument("--epochs", type=int, default=2)
    parser.add_argument("--lr", type=float, default=0.025)
    parser.add_argument("--negatives", type=int, default=5)
    parser.add_argument("--history-window", type=int, default=20)
    parser.add_argument("--history-cap", type=int, default=100)
    parser.add_argument("--max-samples", type=int, default=500000, help="0 means all training pairs")
    parser.add_argument("--test-ratio", type=float, default=0.2)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--eval-output", default="test-results/youtubednn_eval.csv")
    parser.add_argument("--skip-eval", action="store_true")
    args = parser.parse_args()

    random.seed(args.seed)
    data_dir = resolve_data_dir(args.data_dir)
    out_dir = Path(args.out_dir)
    ratings = normalize_columns(load_pickle(data_dir / "ratings.pkl"))
    movies = normalize_columns(load_pickle(data_dir / "movies.pkl"))
    if "timestamp" not in ratings.columns:
        ratings["timestamp"] = ratings.groupby("user_id").cumcount()
    ratings["user_id"] = ratings["user_id"].astype(int)
    ratings["movie_id"] = ratings["movie_id"].astype(int)
    ratings["rating"] = ratings["rating"].astype(float)
    movies["movie_id"] = movies["movie_id"].astype(int)
    min_rating = positive_threshold(ratings, args.min_rating)

    print(f"Data dir: {data_dir}")
    print(f"Positive threshold rating >= {min_rating}")

    if not args.skip_eval:
        print("Training evaluation model on time-based train split...")
        _, train_by_user, _, test_by_user = split_by_time(ratings, args.test_ratio, min_rating, 0.0)
        movie_ids, item_emb, user_item_emb, meta = train_two_tower(
            train_by_user,
            movies,
            args.dim,
            args.epochs,
            args.lr,
            args.negatives,
            args.history_window,
            args.history_cap,
            args.max_samples,
            args.seed,
        )
        evaluate_youtube(
            train_by_user, test_by_user, movie_ids, item_emb, user_item_emb,
            args.history_window, args.eval_output)

    print()
    print("Training final online model on all positive histories...")
    full_histories = build_histories(ratings, min_rating)
    movie_ids, item_emb, user_item_emb, meta = train_two_tower(
        full_histories,
        movies,
        args.dim,
        args.epochs,
        args.lr,
        args.negatives,
        args.history_window,
        args.history_cap,
        args.max_samples,
        args.seed,
    )
    meta.update({
        "version": "youtube-numpy-v1",
        "trained_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "positive_threshold": float(min_rating),
    })
    save_model(out_dir, movie_ids, item_emb, user_item_emb, meta)


if __name__ == "__main__":
    main()
