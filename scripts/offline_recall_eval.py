"""Offline recall evaluation for the movie recommendation homework.

This script does not require Java, Docker, PostgreSQL, Redis, or Elasticsearch.
It reads MovieLens-style pickle files and evaluates a stronger multi-channel
recall layer:

  - popular: global hot movies
  - itemcf: item-to-item collaborative filtering
  - seqcf: sequential item-to-item transition recall
  - ease: linear item-to-item collaborative filtering
  - swing: item co-occurrence with stronger user-activity penalty
  - usercf: user-to-user collaborative filtering
  - content: movie genre/year/rating/popularity feature vectors
  - genre: user preferred genre recall
  - hybrid: balanced weighted reciprocal-rank fusion
  - hybrid_recall: recall-first weighted reciprocal-rank fusion
  - tuned_hybrid: automatically tuned RRF fusion

Example:
    python scripts/offline_recall_eval.py --data-dir scripts/data
"""

from __future__ import annotations

import argparse
import math
import pickle
import random
from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd


def load_pickle(path: Path):
    with path.open("rb") as f:
        return pickle.load(f)


def resolve_data_dir(data_dir: str) -> Path:
    base = Path(data_dir)
    if (base / "ratings.pkl").exists() and (base / "movies.pkl").exists():
        return base
    matches = [
        path for path in base.glob("*/")
        if (path / "ratings.pkl").exists() and (path / "movies.pkl").exists()
    ]
    if matches:
        return matches[0]
    raise FileNotFoundError(f"Cannot find ratings.pkl and movies.pkl under {base}")


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    rename = {}
    for col in df.columns:
        key = col.lower().replace("_", "")
        if key in {"userid", "user"}:
            rename[col] = "user_id"
        elif key in {"movieid", "itemid", "movie"}:
            rename[col] = "movie_id"
        elif key in {"timestamp", "ts", "time"}:
            rename[col] = "timestamp"
        elif key == "startyear":
            rename[col] = "year"
        elif key == "averagerating":
            rename[col] = "imdb_rating"
        elif key == "numvotes":
            rename[col] = "imdb_votes"
        elif key == "runtimeminutes":
            rename[col] = "runtime_minutes"
    return df.rename(columns=rename)


def split_by_time(ratings: pd.DataFrame, test_ratio: float, min_rating: float, valid_ratio: float = 0.0):
    train_rows = []
    valid_by_user: dict[int, set[int]] = {}
    test_by_user: dict[int, set[int]] = {}
    train_by_user: dict[int, list[int]] = {}

    positives = ratings[ratings["rating"] >= min_rating].copy()
    positives = positives.sort_values(["user_id", "timestamp"])

    for user_id, group in positives.groupby("user_id"):
        rows = group.to_dict("records")
        if len(rows) < 5:
            continue
        test_size = max(1, int(round(len(rows) * test_ratio)))
        valid_size = max(1, int(round(len(rows) * valid_ratio))) if valid_ratio > 0 else 0
        if len(rows) - test_size - valid_size < 1:
            valid_size = max(0, len(rows) - test_size - 1)
        test = rows[-test_size:]
        valid = rows[-test_size - valid_size : -test_size] if valid_size > 0 else []
        train = rows[: -test_size - valid_size] if valid_size > 0 else rows[:-test_size]
        if not train:
            continue
        uid = int(user_id)
        train_items = [int(r["movie_id"]) for r in train]
        train_by_user[uid] = train_items
        if valid:
            valid_by_user[uid] = {int(r["movie_id"]) for r in valid}
        test_by_user[uid] = {int(r["movie_id"]) for r in test}
        train_rows.extend(train)

    return pd.DataFrame(train_rows), train_by_user, valid_by_user, test_by_user


def movie_genres(value) -> list[str]:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return []
    if isinstance(value, (list, tuple, set, np.ndarray)):
        return [str(v).strip() for v in value if str(v).strip()]
    return [v.strip() for v in str(value).replace("|", ",").split(",") if v.strip()]


def to_float_or_nan(value) -> float:
    if value is None:
        return float("nan")
    if isinstance(value, str) and value.strip() in {"", "\\N", "nan", "None"}:
        return float("nan")
    try:
        return float(value)
    except (TypeError, ValueError):
        return float("nan")


def build_movie_popular_scores(train: pd.DataFrame) -> dict[int, float]:
    stats = train.groupby("movie_id")["rating"].agg(["count", "mean"]).reset_index()
    global_mean = float(train["rating"].mean())
    m = 20.0
    scores = (
        (stats["count"] / (stats["count"] + m)) * stats["mean"]
        + (m / (stats["count"] + m)) * global_mean
    ) * np.log1p(stats["count"])
    return {int(movie_id): float(score) for movie_id, score in zip(stats["movie_id"], scores)}


def build_popular(train: pd.DataFrame) -> list[int]:
    scores = build_movie_popular_scores(train)
    return [movie_id for movie_id, _ in sorted(scores.items(), key=lambda x: x[1], reverse=True)]


def build_itemcf(train_by_user: dict[int, list[int]], history_cap: int, sim_topn: int):
    item_count: Counter[int] = Counter()
    co_count: dict[int, Counter[int]] = defaultdict(Counter)

    for items in train_by_user.values():
        unique_items = list(dict.fromkeys(items[-history_cap:]))
        if len(unique_items) < 2:
            continue
        weight = 1.0 / math.log2(len(unique_items) + 2.0)
        for item in unique_items:
            item_count[item] += 1
        for i, item_i in enumerate(unique_items):
            for item_j in unique_items[i + 1 :]:
                co_count[item_i][item_j] += weight
                co_count[item_j][item_i] += weight

    sim: dict[int, list[tuple[int, float]]] = {}
    for item_i, related in co_count.items():
        scored = []
        for item_j, cij in related.items():
            denom = math.sqrt(item_count[item_i] * item_count[item_j])
            if denom > 0:
                scored.append((item_j, cij / denom))
        scored.sort(key=lambda x: x[1], reverse=True)
        sim[item_i] = scored[:sim_topn]
    return sim


def build_swing(train_by_user: dict[int, list[int]], history_cap: int, sim_topn: int, alpha: float):
    item_count: Counter[int] = Counter()
    co_count: dict[int, Counter[int]] = defaultdict(Counter)

    for items in train_by_user.values():
        unique_items = list(dict.fromkeys(items[-history_cap:]))
        if len(unique_items) < 2:
            continue
        weight = 1.0 / (alpha + len(unique_items))
        for item in unique_items:
            item_count[item] += 1
        for i, item_i in enumerate(unique_items):
            for item_j in unique_items[i + 1 :]:
                co_count[item_i][item_j] += weight
                co_count[item_j][item_i] += weight

    sim: dict[int, list[tuple[int, float]]] = {}
    for item_i, related in co_count.items():
        scored = []
        for item_j, cij in related.items():
            denom = (item_count[item_i] * item_count[item_j]) ** 0.25
            if denom > 0:
                scored.append((item_j, cij / denom))
        scored.sort(key=lambda x: x[1], reverse=True)
        sim[item_i] = scored[:sim_topn]
    return sim


def build_seqcf(train_by_user: dict[int, list[int]], history_cap: int, sim_topn: int, window: int):
    item_count: Counter[int] = Counter()
    trans_count: dict[int, Counter[int]] = defaultdict(Counter)

    for items in train_by_user.values():
        seq = list(dict.fromkeys(items[-history_cap:]))
        if len(seq) < 2:
            continue
        user_weight = 1.0 / math.log2(len(seq) + 2.0)
        for item in seq:
            item_count[item] += 1
        for i, src in enumerate(seq[:-1]):
            max_j = min(len(seq), i + window + 1)
            for j in range(i + 1, max_j):
                dst = seq[j]
                distance = j - i
                trans_count[src][dst] += user_weight / distance

    sim: dict[int, list[tuple[int, float]]] = {}
    for src, related in trans_count.items():
        scored = []
        for dst, cij in related.items():
            denom = math.sqrt(item_count[src] * item_count[dst])
            if denom > 0:
                scored.append((dst, cij / denom))
        scored.sort(key=lambda x: x[1], reverse=True)
        sim[src] = scored[:sim_topn]
    return sim


def build_ease(train_by_user: dict[int, list[int]], sim_topn: int, l2: float):
    item_ids = sorted({item for items in train_by_user.values() for item in set(items)})
    if not item_ids:
        return {}

    item_index = {movie_id: idx for idx, movie_id in enumerate(item_ids)}
    users = list(train_by_user)
    x = np.zeros((len(users), len(item_ids)), dtype=np.float32)
    for user_idx, user_id in enumerate(users):
        indices = [item_index[item] for item in set(train_by_user[user_id]) if item in item_index]
        if indices:
            x[user_idx, indices] = 1.0

    gram = x.T @ x
    diag = np.diag_indices(len(item_ids))
    gram[diag] += l2
    precision = np.linalg.inv(gram).astype(np.float32)
    denom = -np.diag(precision).copy()
    denom[np.abs(denom) < 1e-12] = 1e-12
    precision /= denom[np.newaxis, :]
    precision[diag] = 0.0

    sim: dict[int, list[tuple[int, float]]] = {}
    topn = min(sim_topn, len(item_ids) - 1)
    if topn <= 0:
        return sim
    for src_idx, src_id in enumerate(item_ids):
        row = precision[src_idx]
        candidate_idx = np.argpartition(row, -topn)[-topn:]
        scored = [
            (item_ids[dst_idx], float(row[dst_idx]))
            for dst_idx in candidate_idx
            if row[dst_idx] > 0 and dst_idx != src_idx
        ]
        scored.sort(key=lambda x: x[1], reverse=True)
        sim[src_id] = scored[:sim_topn]
    return sim


def build_usercf(train_by_user: dict[int, list[int]], user_topn: int, item_user_cap: int):
    item_users: dict[int, list[int]] = defaultdict(list)
    user_item_count = {user_id: len(set(items)) for user_id, items in train_by_user.items()}
    for user_id, items in train_by_user.items():
        for item in set(items):
            item_users[item].append(user_id)

    user_sim: dict[int, Counter[int]] = defaultdict(Counter)
    rng = random.Random(2026)
    for users in item_users.values():
        if len(users) > item_user_cap:
            users = rng.sample(users, item_user_cap)
        weight = 1.0 / math.log2(len(users) + 2.0)
        for i, u in enumerate(users):
            for v in users[i + 1 :]:
                user_sim[u][v] += weight
                user_sim[v][u] += weight

    result: dict[int, list[tuple[int, float]]] = {}
    for u, related in user_sim.items():
        scored = []
        for v, co in related.items():
            denom = math.sqrt(user_item_count.get(u, 1) * user_item_count.get(v, 1))
            scored.append((v, co / denom))
        scored.sort(key=lambda x: x[1], reverse=True)
        result[u] = scored[:user_topn]
    return result


def build_content_vectors(movies: pd.DataFrame, train: pd.DataFrame):
    movie_stats = train.groupby("movie_id")["rating"].agg(["count", "mean"]).reset_index()
    movie_stats = movie_stats.rename(columns={"count": "train_count", "mean": "train_mean"})
    movies = movies.merge(movie_stats, on="movie_id", how="left")
    movies["train_count"] = movies["train_count"].fillna(0)
    movies["train_mean"] = movies["train_mean"].fillna(train["rating"].mean())

    genre_vocab = sorted({g for value in movies.get("genres", []) for g in movie_genres(value)})
    genre_index = {g: i for i, g in enumerate(genre_vocab)}

    years = pd.to_numeric(movies.get("year", pd.Series(dtype=float)), errors="coerce")
    year_min = float(years.min()) if not years.dropna().empty else 1900.0
    year_max = float(years.max()) if not years.dropna().empty else 2020.0
    rating_max = float(train["rating"].max()) if not train.empty else 5.0
    count_max = float(np.log1p(movies["train_count"]).max()) or 1.0

    imdb_ratings = pd.to_numeric(movies.get("imdb_rating", pd.Series(dtype=float)), errors="coerce")
    imdb_rating_max = float(imdb_ratings.max()) if not imdb_ratings.dropna().empty else 10.0
    imdb_votes = pd.to_numeric(movies.get("imdb_votes", pd.Series(dtype=float)), errors="coerce")
    imdb_vote_log = np.log1p(imdb_votes.fillna(0).to_numpy(dtype=np.float64))
    imdb_vote_max = float(np.max(imdb_vote_log)) or 1.0
    runtime = pd.to_numeric(movies.get("runtime_minutes", pd.Series(dtype=float)), errors="coerce")
    runtime_values = runtime.fillna(runtime.median() if not runtime.dropna().empty else 100).to_numpy(dtype=np.float64)
    runtime_min = float(np.min(runtime_values))
    runtime_max = float(np.max(runtime_values))

    dim = len(genre_vocab) + 6
    vectors: dict[int, np.ndarray] = {}
    for _, row in movies.iterrows():
        vec = np.zeros(dim, dtype=np.float32)
        for genre in movie_genres(row.get("genres")):
            if genre in genre_index:
                vec[genre_index[genre]] = 1.0
        base = len(genre_vocab)
        year = to_float_or_nan(row.get("year"))
        if pd.notna(year) and year_max > year_min:
            vec[base] = (year - year_min) / (year_max - year_min)
        vec[base + 1] = float(row["train_mean"]) / rating_max
        vec[base + 2] = math.log1p(float(row["train_count"])) / count_max
        imdb_rating = to_float_or_nan(row.get("imdb_rating"))
        if pd.notna(imdb_rating):
            vec[base + 3] = imdb_rating / imdb_rating_max
        imdb_vote = to_float_or_nan(row.get("imdb_votes"))
        if pd.notna(imdb_vote):
            vec[base + 4] = math.log1p(imdb_vote) / imdb_vote_max
        run = to_float_or_nan(row.get("runtime_minutes"))
        if pd.notna(run) and runtime_max > runtime_min:
            vec[base + 5] = (run - runtime_min) / (runtime_max - runtime_min)
        norm = np.linalg.norm(vec)
        if norm > 0:
            vectors[int(row["movie_id"])] = vec / norm
    return vectors


def build_genre_index(movies: pd.DataFrame, movie_scores: dict[int, float]):
    movie_to_genres: dict[int, list[str]] = {}
    genre_to_movies: dict[str, list[tuple[int, float]]] = defaultdict(list)
    for _, row in movies.iterrows():
        movie_id = int(row["movie_id"])
        genres = movie_genres(row.get("genres"))
        movie_to_genres[movie_id] = genres
        score = movie_scores.get(movie_id, 0.0)
        for genre in genres:
            genre_to_movies[genre].append((movie_id, score))
    for genre in genre_to_movies:
        genre_to_movies[genre].sort(key=lambda x: x[1], reverse=True)
    return movie_to_genres, genre_to_movies


def content_recall(
    history: list[int],
    vectors: dict[int, np.ndarray],
    seen: set[int],
    all_movie_ids: Iterable[int],
    topk: int,
):
    hist_vecs = [vectors[i] for i in history[-50:] if i in vectors]
    if not hist_vecs:
        return []
    weights = np.linspace(0.6, 1.0, num=len(hist_vecs), dtype=np.float32)
    user_vec = np.average(np.stack(hist_vecs), axis=0, weights=weights)
    norm = np.linalg.norm(user_vec)
    if norm == 0:
        return []
    user_vec = user_vec / norm
    scored = []
    for movie_id in all_movie_ids:
        if movie_id in seen or movie_id not in vectors:
            continue
        scored.append((movie_id, float(np.dot(user_vec, vectors[movie_id]))))
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:topk]


def itemcf_recall(history: list[int], sim: dict[int, list[tuple[int, float]]], seen: set[int], topk: int):
    scores: Counter[int] = Counter()
    recent = list(dict.fromkeys(history[-50:]))
    for rank, item in enumerate(reversed(recent)):
        decay = 1.0 / (1.0 + 0.05 * rank)
        for related, score in sim.get(item, []):
            if related not in seen:
                scores[related] += score * decay
    return scores.most_common(topk)


def seqcf_recall(history: list[int], sim: dict[int, list[tuple[int, float]]], seen: set[int], topk: int):
    scores: Counter[int] = Counter()
    recent = list(dict.fromkeys(history[-30:]))
    for rank, item in enumerate(reversed(recent)):
        decay = 1.0 / (1.0 + 0.08 * rank)
        for related, score in sim.get(item, []):
            if related not in seen:
                scores[related] += score * decay
    return scores.most_common(topk)


def ease_recall(history: list[int], sim: dict[int, list[tuple[int, float]]], seen: set[int], topk: int):
    scores: Counter[int] = Counter()
    recent = list(dict.fromkeys(history[-80:]))
    for rank, item in enumerate(reversed(recent)):
        decay = 1.0 / (1.0 + 0.04 * rank)
        for related, score in sim.get(item, []):
            if related not in seen:
                scores[related] += score * decay
    return scores.most_common(topk)


def usercf_recall(
    user_id: int,
    user_sim: dict[int, list[tuple[int, float]]],
    train_by_user: dict[int, list[int]],
    seen: set[int],
    topk: int,
):
    scores: Counter[int] = Counter()
    for similar_user, sim_score in user_sim.get(user_id, []):
        for item in train_by_user.get(similar_user, [])[-100:]:
            if item not in seen:
                scores[item] += sim_score
    return scores.most_common(topk)


def genre_recall(
    history: list[int],
    movie_to_genres: dict[int, list[str]],
    genre_to_movies: dict[str, list[tuple[int, float]]],
    seen: set[int],
    topk: int,
):
    genre_scores: Counter[str] = Counter()
    for rank, movie_id in enumerate(reversed(history[-50:])):
        decay = 1.0 / (1.0 + 0.05 * rank)
        for genre in movie_to_genres.get(movie_id, []):
            genre_scores[genre] += decay
    if not genre_scores:
        return []

    scores: Counter[int] = Counter()
    for genre, genre_weight in genre_scores.most_common(5):
        for movie_id, movie_score in genre_to_movies.get(genre, [])[: topk * 3]:
            if movie_id not in seen:
                scores[movie_id] += genre_weight * (movie_score + 1.0)
    return scores.most_common(topk)


def popular_recall(popular: list[int], seen: set[int], topk: int):
    return [(movie_id, 1.0) for movie_id in popular if movie_id not in seen][:topk]


def merge_rrf(*ranked_lists: tuple[list[tuple[int, float]], float], topk: int, rrf_k: int = 60):
    scores: Counter[int] = Counter()
    for ranked, weight in ranked_lists:
        for rank, (movie_id, _) in enumerate(ranked, start=1):
            scores[movie_id] += weight / (rrf_k + rank)
    return [movie_id for movie_id, _ in scores.most_common(topk)]


def merge_rrf_by_weights(
    channels: dict[str, list[tuple[int, float]]],
    weights: dict[str, float],
    topk: int,
    rrf_k: int = 60,
):
    ranked_lists = [
        (channels[name], weight)
        for name, weight in weights.items()
        if weight > 0 and name in channels
    ]
    return merge_rrf(*ranked_lists, topk=topk, rrf_k=rrf_k)


def dcg_at_k(recs: list[int], test_items: set[int], k: int) -> float:
    score = 0.0
    for rank, movie_id in enumerate(recs[:k], start=1):
        if movie_id in test_items:
            score += 1.0 / math.log2(rank + 1)
    return score


def evaluate(name: str, recs_by_user: dict[int, list[int]], test_by_user: dict[int, set[int]], ks: list[int]):
    rows = []
    users = [u for u in test_by_user if u in recs_by_user]
    for k in ks:
        recall_sum = 0.0
        precision_sum = 0.0
        ndcg_sum = 0.0
        hit_sum = 0.0
        covered = set()
        for user_id in users:
            recs = recs_by_user[user_id][:k]
            test_items = test_by_user[user_id]
            hits = len(set(recs) & test_items)
            recall_sum += hits / len(test_items)
            precision_sum += hits / k
            ideal_hits = min(len(test_items), k)
            ideal_dcg = sum(1.0 / math.log2(rank + 1) for rank in range(1, ideal_hits + 1))
            ndcg_sum += dcg_at_k(recs, test_items, k) / ideal_dcg if ideal_dcg > 0 else 0.0
            hit_sum += 1.0 if hits > 0 else 0.0
            covered.update(recs)
        rows.append(
            {
                "method": name,
                "k": k,
                "recall": recall_sum / len(users),
                "precision": precision_sum / len(users),
                "ndcg": ndcg_sum / len(users),
                "hit_rate": hit_sum / len(users),
                "coverage": len(covered),
            }
        )
    return rows


def metric_at_k(recs: list[int], test_items: set[int], metric: str, k: int) -> float:
    hits = len(set(recs[:k]) & test_items)
    if metric == "precision":
        return hits / k
    if metric == "ndcg":
        ideal_hits = min(len(test_items), k)
        ideal_dcg = sum(1.0 / math.log2(rank + 1) for rank in range(1, ideal_hits + 1))
        return dcg_at_k(recs, test_items, k) / ideal_dcg if ideal_dcg > 0 else 0.0
    return hits / len(test_items)


def candidate_weight_profiles():
    base = [
        {"itemcf": 1.20, "swing": 1.10, "usercf": 0.90, "content": 0.65, "genre": 0.80, "popular": 0.25},
        {"itemcf": 2.00, "usercf": 1.35, "seqcf": 1.10, "ease": 1.20, "swing": 1.00, "genre": 0.35, "content": 0.20, "popular": 0.05},
        {"itemcf": 2.20, "usercf": 1.60, "seqcf": 1.20, "ease": 1.40, "swing": 0.80, "genre": 0.20, "content": 0.10, "popular": 0.00},
        {"itemcf": 1.60, "usercf": 1.60, "seqcf": 1.00, "ease": 1.20, "swing": 1.20, "genre": 0.40, "content": 0.20, "popular": 0.05},
    ]
    grid = []
    for itemcf in [1.6, 2.0, 2.4]:
        for usercf in [1.0, 1.4, 1.8]:
            for ease in [0.8, 1.2, 1.6]:
                for swing in [0.7, 1.0, 1.3]:
                    for genre in [0.2, 0.5]:
                        for content in [0.1, 0.3]:
                            grid.append({
                                "itemcf": itemcf,
                                "usercf": usercf,
                                "seqcf": 1.1,
                                "ease": ease,
                                "swing": swing,
                                "genre": genre,
                                "content": content,
                                "popular": 0.05,
                            })
    return base + grid


def tune_rrf_weights(
    channels_by_user: dict[int, dict[str, list[tuple[int, float]]]],
    test_by_user: dict[int, set[int]],
    metric: str,
    k: int,
    max_users: int,
    seed: int,
):
    users = [u for u in test_by_user if u in channels_by_user]
    if max_users > 0 and len(users) > max_users:
        rng = random.Random(seed)
        users = rng.sample(users, max_users)

    best_score = -1.0
    best_weights = {}
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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", default="scripts/data")
    parser.add_argument("--test-ratio", type=float, default=0.2)
    parser.add_argument("--valid-ratio", type=float, default=0.1)
    parser.add_argument("--min-rating", default="auto")
    parser.add_argument("--history-cap", type=int, default=100)
    parser.add_argument("--sim-topn", type=int, default=200)
    parser.add_argument("--swing-alpha", type=float, default=5.0)
    parser.add_argument("--seq-window", type=int, default=5)
    parser.add_argument("--ease-reg", type=float, default=500.0)
    parser.add_argument("--user-topn", type=int, default=80)
    parser.add_argument("--item-user-cap", type=int, default=600)
    parser.add_argument("--max-users", type=int, default=0, help="0 means all users")
    parser.add_argument("--tune-weights", action="store_true")
    parser.add_argument("--tune-metric", choices=["recall", "precision", "ndcg"], default="recall")
    parser.add_argument("--tune-k", type=int, default=100)
    parser.add_argument("--tune-users", type=int, default=1200)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output", default="")
    args = parser.parse_args()

    random.seed(args.seed)
    data_dir = resolve_data_dir(args.data_dir)
    ratings = normalize_columns(load_pickle(data_dir / "ratings.pkl"))
    movies = normalize_columns(load_pickle(data_dir / "movies.pkl"))

    required = {"user_id", "movie_id", "rating"}
    missing = required - set(ratings.columns)
    if missing:
        raise ValueError(f"ratings.pkl missing columns: {sorted(missing)}")
    if "timestamp" not in ratings.columns:
        ratings["timestamp"] = ratings.groupby("user_id").cumcount()
    if "movie_id" not in movies.columns:
        raise ValueError("movies.pkl missing movie_id column")

    ratings["user_id"] = ratings["user_id"].astype(int)
    ratings["movie_id"] = ratings["movie_id"].astype(int)
    ratings["rating"] = ratings["rating"].astype(float)
    movies["movie_id"] = movies["movie_id"].astype(int)

    if args.min_rating == "auto":
        min_rating = 4.0 if ratings["rating"].max() <= 5 else 8.0
    else:
        min_rating = float(args.min_rating)

    valid_ratio = args.valid_ratio if args.tune_weights else 0.0
    train, train_by_user, valid_by_user, test_by_user = split_by_time(
        ratings, args.test_ratio, min_rating, valid_ratio)
    if args.max_users > 0:
        keep_users = set(random.sample(list(test_by_user), min(args.max_users, len(test_by_user))))
        train_by_user = {u: v for u, v in train_by_user.items() if u in keep_users}
        valid_by_user = {u: v for u, v in valid_by_user.items() if u in keep_users}
        test_by_user = {u: v for u, v in test_by_user.items() if u in keep_users}

    all_movie_ids = sorted(set(movies["movie_id"].astype(int)))
    print(f"Data dir: {data_dir}")
    print(f"Users evaluated: {len(test_by_user)}")
    if args.tune_weights:
        print(f"Users for validation tuning: {len(valid_by_user)}")
    print(f"Train positives: {len(train):,}")
    print(f"Movies: {len(all_movie_ids):,}")
    print(f"Positive threshold rating >= {min_rating}")

    print("Building popular and content indexes...")
    movie_scores = build_movie_popular_scores(train)
    popular = build_popular(train)
    content_vectors = build_content_vectors(movies, train)
    movie_to_genres, genre_to_movies = build_genre_index(movies, movie_scores)

    print("Building ItemCF index...")
    item_sim = build_itemcf(train_by_user, args.history_cap, args.sim_topn)

    print("Building Swing index...")
    swing_sim = build_swing(train_by_user, args.history_cap, args.sim_topn, args.swing_alpha)

    print("Building SeqCF index...")
    seq_sim = build_seqcf(train_by_user, args.history_cap, args.sim_topn, args.seq_window)

    print("Building EASE index...")
    ease_sim = build_ease(train_by_user, args.sim_topn, args.ease_reg)

    print("Building UserCF index...")
    user_sim = build_usercf(train_by_user, args.user_topn, args.item_user_cap)

    recs = {
        "popular": {},
        "itemcf": {},
        "seqcf": {},
        "ease": {},
        "swing": {},
        "usercf": {},
        "content": {},
        "genre": {},
        "hybrid": {},
        "hybrid_recall": {},
    }
    channels_by_user: dict[int, dict[str, list[tuple[int, float]]]] = {}
    recall_pool_k = 300
    print("Generating recommendations...")
    for user_id, history in train_by_user.items():
        seen = set(history)
        pop = popular_recall(popular, seen, recall_pool_k)
        itemcf = itemcf_recall(history, item_sim, seen, recall_pool_k)
        seqcf = seqcf_recall(history, seq_sim, seen, recall_pool_k)
        ease = ease_recall(history, ease_sim, seen, recall_pool_k)
        swing = itemcf_recall(history, swing_sim, seen, recall_pool_k)
        usercf = usercf_recall(user_id, user_sim, train_by_user, seen, recall_pool_k)
        content = content_recall(history, content_vectors, seen, all_movie_ids, recall_pool_k)
        genre = genre_recall(history, movie_to_genres, genre_to_movies, seen, recall_pool_k)
        channels = {
            "popular": pop,
            "itemcf": itemcf,
            "seqcf": seqcf,
            "ease": ease,
            "swing": swing,
            "usercf": usercf,
            "content": content,
            "genre": genre,
        }
        channels_by_user[user_id] = channels
        hybrid = merge_rrf(
            (itemcf, 1.20),
            (seqcf, 0.90),
            (ease, 1.10),
            (swing, 1.10),
            (usercf, 0.90),
            (content, 0.65),
            (genre, 0.80),
            (pop, 0.25),
            topk=recall_pool_k,
        )
        hybrid_recall = merge_rrf(
            (itemcf, 2.00),
            (usercf, 1.35),
            (seqcf, 1.10),
            (ease, 1.25),
            (swing, 1.00),
            (genre, 0.35),
            (content, 0.20),
            (pop, 0.05),
            topk=recall_pool_k,
        )
        recs["popular"][user_id] = [i for i, _ in pop]
        recs["itemcf"][user_id] = [i for i, _ in itemcf]
        recs["seqcf"][user_id] = [i for i, _ in seqcf]
        recs["ease"][user_id] = [i for i, _ in ease]
        recs["swing"][user_id] = [i for i, _ in swing]
        recs["usercf"][user_id] = [i for i, _ in usercf]
        recs["content"][user_id] = [i for i, _ in content]
        recs["genre"][user_id] = [i for i, _ in genre]
        recs["hybrid"][user_id] = hybrid
        recs["hybrid_recall"][user_id] = hybrid_recall

    if args.tune_weights:
        best_weights, best_score, tuned_users = tune_rrf_weights(
            channels_by_user,
            valid_by_user if valid_by_user else test_by_user,
            args.tune_metric,
            args.tune_k,
            args.tune_users,
            args.seed,
        )
        print()
        print(f"Tuned RRF weights on {tuned_users} users by {args.tune_metric}@{args.tune_k}:")
        print(best_weights)
        print(f"Tuning score: {best_score:.6f}")
        recs["tuned_hybrid"] = {
            user_id: merge_rrf_by_weights(channels, best_weights, topk=recall_pool_k)
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
    print("Precision:")
    print(result.pivot(index="method", columns="k", values="precision").round(4))
    print()
    print("NDCG:")
    print(result.pivot(index="method", columns="k", values="ndcg").round(4))
    print()
    print("HitRate:")
    print(result.pivot(index="method", columns="k", values="hit_rate").round(4))
    print()
    print("Coverage:")
    print(result.pivot(index="method", columns="k", values="coverage").astype(int))

    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        result.to_csv(output, index=False, encoding="utf-8-sig")
        print(f"\nSaved metrics to {output}")


if __name__ == "__main__":
    main()
