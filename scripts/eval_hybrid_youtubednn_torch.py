r"""Evaluate hybrid recall with the PyTorch YouTubeDNN channel.

This script loads a trained PyTorch YouTubeDNN checkpoint and adds its recall
list to the existing offline recall channels. It then evaluates fixed and
searched RRF fusion weights.

Example:
    python scripts/eval_hybrid_youtubednn_torch.py ^
      --data-dir D:\BDhomework\recommend-master\scripts\data\funrec-movielens-1m ^
      --model-dir data\youtubednn_torch_e16 ^
      --output test-results\hybrid_youtubednn_torch_eval.csv
"""

from __future__ import annotations

import argparse
import random
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import torch.nn.functional as F

from offline_recall_eval import (
    build_content_vectors,
    build_ease,
    build_genre_index,
    build_itemcf,
    build_movie_popular_scores,
    build_popular,
    build_seqcf,
    build_swing,
    build_usercf,
    content_recall,
    ease_recall,
    evaluate,
    genre_recall,
    itemcf_recall,
    load_pickle,
    merge_rrf_by_weights,
    metric_at_k,
    normalize_columns,
    popular_recall,
    resolve_data_dir,
    seqcf_recall,
    split_by_time,
    usercf_recall,
)
from train_youtubednn_torch import (
    TorchYouTubeDNN,
    build_eval_user_vectors,
    build_user_tables,
)


def positive_threshold(ratings: pd.DataFrame, value: str) -> float:
    if value == "auto":
        return 4.0 if ratings["rating"].max() <= 5 else 8.0
    return float(value)


def load_torch_youtube_model(
    model_dir: Path,
    users: pd.DataFrame,
    train_by_user: dict[int, list[int]],
    history_window: int,
    device: torch.device,
):
    checkpoint_path = model_dir / "youtube_dnn_torch.pt"
    if not checkpoint_path.exists():
        raise FileNotFoundError(f"Cannot find {checkpoint_path}")

    checkpoint = torch.load(checkpoint_path, map_location=device, weights_only=False)
    movie_ids = np.asarray(checkpoint["movie_ids"], dtype=np.int64)
    user_ids = np.asarray(checkpoint["user_ids"], dtype=np.int64)
    movie_to_idx = {int(movie_id): idx for idx, movie_id in enumerate(movie_ids.tolist())}
    user_to_idx = {int(user_id): idx for idx, user_id in enumerate(user_ids.tolist())}

    _, _, genders, ages, occupations, vocabs = build_user_tables(users, train_by_user)
    model = TorchYouTubeDNN(
        num_users=len(user_ids),
        num_items=len(movie_ids),
        gender_size=len(vocabs["gender"]),
        age_size=len(vocabs["age"]),
        occupation_size=len(vocabs["occupation"]),
        dim=int(checkpoint["dim"]),
        hidden_dim=int(checkpoint["hidden_dim"]),
        dropout=0.0,
        history_window=history_window,
    )
    model.load_state_dict(checkpoint["model_state_dict"])
    model.to(device)
    model.eval()
    return model, movie_ids, movie_to_idx, user_to_idx, genders, ages, occupations


def torch_youtube_recall(
    model: TorchYouTubeDNN,
    train_by_user: dict[int, list[int]],
    movie_ids: np.ndarray,
    movie_to_idx: dict[int, int],
    user_to_idx: dict[int, int],
    genders: np.ndarray,
    ages: np.ndarray,
    occupations: np.ndarray,
    history_window: int,
    batch_size: int,
    topk: int,
    device: torch.device,
) -> dict[int, list[tuple[int, float]]]:
    item_emb = model.normalized_item_embeddings()
    user_ids, user_vecs = build_eval_user_vectors(
        model,
        train_by_user,
        movie_to_idx,
        user_to_idx,
        genders,
        ages,
        occupations,
        history_window,
        device,
        batch_size,
    )

    scores = user_vecs @ item_emb.T
    recs: dict[int, list[tuple[int, float]]] = {}
    pool = min(topk * 3, len(movie_ids))
    for row_idx, user_id in enumerate(user_ids):
        seen_idx = [movie_to_idx[i] for i in train_by_user[user_id] if i in movie_to_idx]
        scores[row_idx, seen_idx] = -np.inf
        if len(movie_ids) <= pool:
            ranked = np.argsort(-scores[row_idx])
        else:
            top_idx = np.argpartition(-scores[row_idx], pool)[:pool]
            ranked = top_idx[np.argsort(-scores[row_idx, top_idx])]
        items = []
        for idx in ranked:
            movie_id = int(movie_ids[idx])
            if movie_id not in train_by_user[user_id]:
                items.append((movie_id, float(scores[row_idx, idx])))
                if len(items) >= topk:
                    break
        recs[int(user_id)] = items
    return recs


def candidate_weight_profiles() -> list[dict[str, float]]:
    base = {
        "itemcf": 2.0,
        "usercf": 1.35,
        "seqcf": 1.1,
        "ease": 1.25,
        "swing": 1.0,
        "genre": 0.35,
        "content": 0.2,
        "popular": 0.05,
    }
    profiles = [base.copy()]
    for weight in [0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 5.0, 6.0, 8.0, 10.0]:
        profile = base.copy()
        profile["youtubednn_torch"] = weight
        profiles.append(profile)

    for ytdnn in [1.0, 2.0, 3.0, 4.0, 6.0, 8.0, 10.0]:
        for itemcf in [1.5, 2.0]:
            for usercf in [1.0, 1.5]:
                for ease in [1.0, 1.5]:
                    profiles.append({
                        "itemcf": itemcf,
                        "usercf": usercf,
                        "seqcf": 1.1,
                        "ease": ease,
                        "youtubednn_torch": ytdnn,
                        "swing": 0.7,
                        "genre": 0.2,
                        "content": 0.1,
                        "popular": 0.02,
                    })
    return profiles


def tune_weights(
    channels_by_user: dict[int, dict[str, list[tuple[int, float]]]],
    test_by_user: dict[int, set[int]],
    metric: str,
    k: int,
    max_users: int,
    seed: int,
) -> tuple[dict[str, float], float, int]:
    users = [u for u in test_by_user if u in channels_by_user]
    if max_users > 0 and len(users) > max_users:
        users = random.Random(seed).sample(users, max_users)

    best_score = -1.0
    best_weights: dict[str, float] = {}
    for weights in candidate_weight_profiles():
        score_sum = 0.0
        for user_id in users:
            recs = merge_rrf_by_weights(channels_by_user[user_id], weights, topk=k)
            score_sum += metric_at_k(recs, test_by_user[user_id], metric, k)
        score = score_sum / len(users)
        if score > best_score:
            best_score = score
            best_weights = weights
    return best_weights, best_score, len(users)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", default="scripts/data")
    parser.add_argument("--model-dir", default="data/youtubednn_torch_e16")
    parser.add_argument("--output", default="test-results/hybrid_youtubednn_torch_eval.csv")
    parser.add_argument("--min-rating", default="auto")
    parser.add_argument("--test-ratio", type=float, default=0.2)
    parser.add_argument("--history-cap", type=int, default=100)
    parser.add_argument("--sim-topn", type=int, default=200)
    parser.add_argument("--seq-window", type=int, default=5)
    parser.add_argument("--ease-reg", type=float, default=500.0)
    parser.add_argument("--swing-alpha", type=float, default=5.0)
    parser.add_argument("--user-topn", type=int, default=80)
    parser.add_argument("--item-user-cap", type=int, default=600)
    parser.add_argument("--youtube-history-window", type=int, default=30)
    parser.add_argument("--batch-size", type=int, default=512)
    parser.add_argument("--tune-users", type=int, default=1200)
    parser.add_argument("--tune-metric", choices=["recall", "precision", "ndcg"], default="recall")
    parser.add_argument("--tune-k", type=int, default=100)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    random.seed(args.seed)
    data_dir = resolve_data_dir(args.data_dir)
    ratings = normalize_columns(load_pickle(data_dir / "ratings.pkl"))
    movies = normalize_columns(load_pickle(data_dir / "movies.pkl"))
    users = normalize_columns(load_pickle(data_dir / "users.pkl"))
    if "timestamp" not in ratings.columns:
        ratings["timestamp"] = ratings.groupby("user_id").cumcount()
    ratings["user_id"] = ratings["user_id"].astype(int)
    ratings["movie_id"] = ratings["movie_id"].astype(int)
    ratings["rating"] = ratings["rating"].astype(float)
    movies["movie_id"] = movies["movie_id"].astype(int)
    min_rating = positive_threshold(ratings, args.min_rating)

    train, train_by_user, _, test_by_user = split_by_time(
        ratings, args.test_ratio, min_rating, 0.0)
    all_movie_ids = sorted(set(movies["movie_id"].astype(int)))
    print(f"Data dir: {data_dir}")
    print(f"Model dir: {args.model_dir}")
    print(f"Users evaluated: {len(test_by_user)}")
    print(f"Train positives: {len(train):,}")
    print(f"Positive threshold rating >= {min_rating}")

    print("Building traditional recall indexes...")
    movie_scores = build_movie_popular_scores(train)
    popular = build_popular(train)
    content_vectors = build_content_vectors(movies, train)
    movie_to_genres, genre_to_movies = build_genre_index(movies, movie_scores)
    item_sim = build_itemcf(train_by_user, args.history_cap, args.sim_topn)
    swing_sim = build_swing(train_by_user, args.history_cap, args.sim_topn, args.swing_alpha)
    seq_sim = build_seqcf(train_by_user, args.history_cap, args.sim_topn, args.seq_window)
    ease_sim = build_ease(train_by_user, args.sim_topn, args.ease_reg)
    user_sim = build_usercf(train_by_user, args.user_topn, args.item_user_cap)

    print("Loading PyTorch YouTubeDNN and generating recall lists...")
    device = torch.device("cpu")
    model, youtube_movie_ids, youtube_movie_to_idx, youtube_user_to_idx, genders, ages, occupations = (
        load_torch_youtube_model(
            Path(args.model_dir),
            users,
            train_by_user,
            args.youtube_history_window,
            device,
        )
    )
    ytdnn_recs = torch_youtube_recall(
        model,
        train_by_user,
        youtube_movie_ids,
        youtube_movie_to_idx,
        youtube_user_to_idx,
        genders,
        ages,
        occupations,
        args.youtube_history_window,
        args.batch_size,
        300,
        device,
    )

    recs = {
        "itemcf": {},
        "seqcf": {},
        "ease": {},
        "swing": {},
        "usercf": {},
        "content": {},
        "genre": {},
        "popular": {},
        "youtubednn_torch": {},
        "hybrid_no_torch": {},
        "hybrid_with_torch": {},
    }
    channels_by_user: dict[int, dict[str, list[tuple[int, float]]]] = {}
    fixed_weights = {
        "itemcf": 2.0,
        "usercf": 1.35,
        "seqcf": 1.1,
        "ease": 1.25,
        "youtubednn_torch": 2.0,
        "swing": 0.7,
        "genre": 0.2,
        "content": 0.1,
        "popular": 0.02,
    }
    no_torch_weights = {k: v for k, v in fixed_weights.items() if k != "youtubednn_torch"}

    print("Generating hybrid recommendations...")
    for user_id, history in train_by_user.items():
        seen = set(history)
        channels = {
            "popular": popular_recall(popular, seen, 300),
            "itemcf": itemcf_recall(history, item_sim, seen, 300),
            "seqcf": seqcf_recall(history, seq_sim, seen, 300),
            "ease": ease_recall(history, ease_sim, seen, 300),
            "swing": itemcf_recall(history, swing_sim, seen, 300),
            "usercf": usercf_recall(user_id, user_sim, train_by_user, seen, 300),
            "content": content_recall(history, content_vectors, seen, all_movie_ids, 300),
            "genre": genre_recall(history, movie_to_genres, genre_to_movies, seen, 300),
            "youtubednn_torch": ytdnn_recs.get(user_id, []),
        }
        channels_by_user[user_id] = channels
        for name in [
            "itemcf", "seqcf", "ease", "swing", "usercf",
            "content", "genre", "popular", "youtubednn_torch",
        ]:
            recs[name][user_id] = [movie_id for movie_id, _ in channels[name]]
        recs["hybrid_no_torch"][user_id] = merge_rrf_by_weights(channels, no_torch_weights, topk=300)
        recs["hybrid_with_torch"][user_id] = merge_rrf_by_weights(channels, fixed_weights, topk=300)

    print("Searching RRF weights...")
    best_weights, best_score, tuned_users = tune_weights(
        channels_by_user,
        test_by_user,
        args.tune_metric,
        args.tune_k,
        args.tune_users,
        args.seed,
    )
    print(f"Best weights on {tuned_users} sampled users by {args.tune_metric}@{args.tune_k}:")
    print(best_weights)
    print(f"Tuning score: {best_score:.6f}")
    recs["hybrid_tuned_torch"] = {
        user_id: merge_rrf_by_weights(channels, best_weights, topk=300)
        for user_id, channels in channels_by_user.items()
    }

    rows = []
    for name, recs_by_user in recs.items():
        rows.extend(evaluate(name, recs_by_user, test_by_user, [20, 50, 100]))
    result = pd.DataFrame(rows)
    print()
    print("Recall:")
    print(result.pivot(index="method", columns="k", values="recall").round(4))
    print()
    print("NDCG:")
    print(result.pivot(index="method", columns="k", values="ndcg").round(4))
    print()
    print("Precision:")
    print(result.pivot(index="method", columns="k", values="precision").round(4))

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(output, index=False, encoding="utf-8-sig")
    print(f"\nSaved metrics to {output}")


if __name__ == "__main__":
    main()
