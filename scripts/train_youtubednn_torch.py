"""Train a PyTorch YouTubeDNN-style recall model.

This is a fuller offline implementation than scripts/train_youtubednn.py:

  - user tower: user id/profile embeddings + weighted history pooling + MLP
  - item tower: trainable item embedding table
  - objective: full-softmax next-positive-item classification
  - evaluation: time-based split with Recall/Precision/NDCG/HitRate/Coverage

The dataset is small enough for full-softmax CPU training on MovieLens 1M.
Outputs are written under data/youtubednn_torch by default so this script does
not overwrite the currently online NumPy YouTubeDNN artifacts.
"""

from __future__ import annotations

import argparse
import json
import math
import random
import time
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import DataLoader, TensorDataset

from offline_recall_eval import (
    evaluate,
    load_pickle,
    normalize_columns,
    resolve_data_dir,
    split_by_time,
)


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


def bucket_age(value) -> str:
    try:
        age = int(value)
    except (TypeError, ValueError):
        return "unknown"
    if age <= 0:
        return "unknown"
    if age < 18:
        return "under18"
    if age < 25:
        return "18-24"
    if age < 35:
        return "25-34"
    if age < 45:
        return "35-44"
    if age < 50:
        return "45-49"
    if age < 56:
        return "50-55"
    return "56+"


def build_user_tables(
    users: pd.DataFrame,
    histories: dict[int, list[int]],
) -> tuple[np.ndarray, dict[int, int], np.ndarray, np.ndarray, np.ndarray, dict[str, dict[str, int]]]:
    user_ids = np.array(sorted(histories), dtype=np.int64)
    user_to_idx = {int(user_id): idx for idx, user_id in enumerate(user_ids.tolist())}

    users = normalize_columns(users.copy())
    if "user_id" not in users.columns:
        users["user_id"] = []
    users["user_id"] = users["user_id"].astype(int)
    user_rows = users.set_index("user_id").to_dict("index")

    gender_vocab = {"unknown": 0}
    age_vocab = {"unknown": 0}
    occupation_vocab = {"unknown": 0}

    raw_profiles = []
    for user_id in user_ids:
        row = user_rows.get(int(user_id), {})
        gender = str(row.get("gender", "unknown") or "unknown")
        age = bucket_age(row.get("age"))
        occupation = str(row.get("occupation", "unknown") or "unknown")
        raw_profiles.append((gender, age, occupation))
        gender_vocab.setdefault(gender, len(gender_vocab))
        age_vocab.setdefault(age, len(age_vocab))
        occupation_vocab.setdefault(occupation, len(occupation_vocab))

    genders = np.array([gender_vocab[g] for g, _, _ in raw_profiles], dtype=np.int64)
    ages = np.array([age_vocab[a] for _, a, _ in raw_profiles], dtype=np.int64)
    occupations = np.array([occupation_vocab[o] for _, _, o in raw_profiles], dtype=np.int64)
    vocabs = {
        "gender": gender_vocab,
        "age": age_vocab,
        "occupation": occupation_vocab,
    }
    return user_ids, user_to_idx, genders, ages, occupations, vocabs


def build_training_arrays(
    histories: dict[int, list[int]],
    movie_to_idx: dict[int, int],
    user_to_idx: dict[int, int],
    history_window: int,
    history_cap: int,
    max_samples: int,
    seed: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    pairs: list[tuple[int, list[int], int]] = []
    for user_id, items in histories.items():
        if user_id not in user_to_idx:
            continue
        seq = [movie_to_idx[i] for i in items[-history_cap:] if i in movie_to_idx]
        seq = list(dict.fromkeys(seq))
        if len(seq) < 2:
            continue
        user_idx = user_to_idx[user_id]
        for pos in range(1, len(seq)):
            pairs.append((user_idx, seq[max(0, pos - history_window):pos], seq[pos]))

    if max_samples > 0 and len(pairs) > max_samples:
        rng = random.Random(seed)
        pairs = rng.sample(pairs, max_samples)

    user_idx_arr = np.empty(len(pairs), dtype=np.int64)
    hist_arr = np.zeros((len(pairs), history_window), dtype=np.int64)
    target_arr = np.empty(len(pairs), dtype=np.int64)
    for row_idx, (user_idx, hist, target) in enumerate(pairs):
        user_idx_arr[row_idx] = user_idx
        token_hist = [item_idx + 1 for item_idx in hist[-history_window:]]
        hist_arr[row_idx, -len(token_hist):] = token_hist
        target_arr[row_idx] = target
    return user_idx_arr, hist_arr, target_arr


class TorchYouTubeDNN(nn.Module):
    def __init__(
        self,
        num_users: int,
        num_items: int,
        gender_size: int,
        age_size: int,
        occupation_size: int,
        dim: int,
        hidden_dim: int,
        dropout: float,
        history_window: int,
    ) -> None:
        super().__init__()
        self.history_window = history_window
        self.item_embedding = nn.Embedding(num_items + 1, dim, padding_idx=0)
        self.user_embedding = nn.Embedding(num_users, dim)
        self.gender_embedding = nn.Embedding(gender_size, max(2, dim // 8))
        self.age_embedding = nn.Embedding(age_size, max(2, dim // 8))
        self.occupation_embedding = nn.Embedding(occupation_size, max(4, dim // 4))
        profile_dim = dim + max(2, dim // 8) + max(2, dim // 8) + max(4, dim // 4)
        self.user_tower = nn.Sequential(
            nn.Linear(dim + profile_dim, hidden_dim),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim, dim),
        )
        self.item_bias = nn.Parameter(torch.zeros(num_items))
        weights = torch.linspace(0.6, 1.0, steps=history_window).view(1, history_window, 1)
        self.register_buffer("history_weights", weights)
        self.reset_parameters()

    def reset_parameters(self) -> None:
        nn.init.normal_(self.item_embedding.weight, mean=0.0, std=0.02)
        nn.init.normal_(self.user_embedding.weight, mean=0.0, std=0.02)
        nn.init.normal_(self.gender_embedding.weight, mean=0.0, std=0.02)
        nn.init.normal_(self.age_embedding.weight, mean=0.0, std=0.02)
        nn.init.normal_(self.occupation_embedding.weight, mean=0.0, std=0.02)
        with torch.no_grad():
            self.item_embedding.weight[0].zero_()

    def encode_user(
        self,
        user_idx: torch.Tensor,
        gender_idx: torch.Tensor,
        age_idx: torch.Tensor,
        occupation_idx: torch.Tensor,
        hist_tokens: torch.Tensor,
    ) -> torch.Tensor:
        hist_emb = self.item_embedding(hist_tokens)
        mask = hist_tokens.ne(0).float().unsqueeze(-1)
        weights = self.history_weights * mask
        denom = weights.sum(dim=1).clamp_min(1.0)
        hist_vec = (hist_emb * weights).sum(dim=1) / denom

        profile = torch.cat([
            self.user_embedding(user_idx),
            self.gender_embedding(gender_idx),
            self.age_embedding(age_idx),
            self.occupation_embedding(occupation_idx),
        ], dim=1)
        user_vec = self.user_tower(torch.cat([hist_vec, profile], dim=1))
        return user_vec

    def forward(
        self,
        user_idx: torch.Tensor,
        gender_idx: torch.Tensor,
        age_idx: torch.Tensor,
        occupation_idx: torch.Tensor,
        hist_tokens: torch.Tensor,
    ) -> torch.Tensor:
        user_vec = self.encode_user(user_idx, gender_idx, age_idx, occupation_idx, hist_tokens)
        item_vecs = self.item_embedding.weight[1:]
        return user_vec @ item_vecs.t() + self.item_bias

    def normalized_item_embeddings(self) -> np.ndarray:
        with torch.no_grad():
            emb = self.item_embedding.weight[1:].detach().cpu().numpy().astype(np.float64)
        norms = np.linalg.norm(emb, axis=1, keepdims=True)
        return emb / np.where(norms == 0.0, 1.0, norms)


def train_model(
    model: TorchYouTubeDNN,
    arrays: tuple[np.ndarray, np.ndarray, np.ndarray],
    genders: np.ndarray,
    ages: np.ndarray,
    occupations: np.ndarray,
    epochs: int,
    batch_size: int,
    lr: float,
    weight_decay: float,
    device: torch.device,
) -> None:
    user_idx_arr, hist_arr, target_arr = arrays
    dataset = TensorDataset(
        torch.from_numpy(user_idx_arr),
        torch.from_numpy(hist_arr),
        torch.from_numpy(target_arr),
    )
    loader = DataLoader(dataset, batch_size=batch_size, shuffle=True, num_workers=0)
    optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=weight_decay)
    model.to(device)
    gender_t = torch.from_numpy(genders).to(device)
    age_t = torch.from_numpy(ages).to(device)
    occupation_t = torch.from_numpy(occupations).to(device)

    for epoch in range(1, epochs + 1):
        model.train()
        total_loss = 0.0
        total_seen = 0
        started = time.time()
        for user_idx, hist_tokens, target in loader:
            user_idx = user_idx.to(device)
            hist_tokens = hist_tokens.to(device)
            target = target.to(device)
            logits = model(
                user_idx,
                gender_t[user_idx],
                age_t[user_idx],
                occupation_t[user_idx],
                hist_tokens,
            )
            loss = F.cross_entropy(logits, target)
            optimizer.zero_grad(set_to_none=True)
            loss.backward()
            optimizer.step()
            total_loss += float(loss.item()) * len(user_idx)
            total_seen += len(user_idx)
        print(
            f"Epoch {epoch}/{epochs} loss={total_loss / max(1, total_seen):.4f} "
            f"time={time.time() - started:.1f}s"
        )


def build_eval_user_vectors(
    model: TorchYouTubeDNN,
    train_by_user: dict[int, list[int]],
    movie_to_idx: dict[int, int],
    user_to_idx: dict[int, int],
    genders: np.ndarray,
    ages: np.ndarray,
    occupations: np.ndarray,
    history_window: int,
    device: torch.device,
    batch_size: int,
) -> tuple[list[int], np.ndarray]:
    user_ids = [user_id for user_id in train_by_user if user_id in user_to_idx]
    hist = np.zeros((len(user_ids), history_window), dtype=np.int64)
    user_idx_arr = np.empty(len(user_ids), dtype=np.int64)
    for row_idx, user_id in enumerate(user_ids):
        user_idx = user_to_idx[user_id]
        user_idx_arr[row_idx] = user_idx
        hist_idx = [movie_to_idx[i] + 1 for i in train_by_user[user_id][-history_window:] if i in movie_to_idx]
        if hist_idx:
            hist[row_idx, -len(hist_idx):] = hist_idx[-history_window:]

    model.eval()
    vectors = []
    gender_t = torch.from_numpy(genders).to(device)
    age_t = torch.from_numpy(ages).to(device)
    occupation_t = torch.from_numpy(occupations).to(device)
    with torch.no_grad():
        for start in range(0, len(user_ids), batch_size):
            end = start + batch_size
            user_t = torch.from_numpy(user_idx_arr[start:end]).to(device)
            hist_t = torch.from_numpy(hist[start:end]).to(device)
            vec = model.encode_user(
                user_t,
                gender_t[user_t],
                age_t[user_t],
                occupation_t[user_t],
                hist_t,
            )
            vec = F.normalize(vec, dim=1)
            vectors.append(vec.cpu().numpy())
    return user_ids, np.vstack(vectors)


def evaluate_model(
    model: TorchYouTubeDNN,
    train_by_user: dict[int, list[int]],
    test_by_user: dict[int, set[int]],
    movie_ids: np.ndarray,
    movie_to_idx: dict[int, int],
    user_to_idx: dict[int, int],
    genders: np.ndarray,
    ages: np.ndarray,
    occupations: np.ndarray,
    history_window: int,
    device: torch.device,
    batch_size: int,
    output: str,
) -> pd.DataFrame:
    item_emb = model.normalized_item_embeddings()
    user_ids, user_vecs = build_eval_user_vectors(
        model, train_by_user, movie_to_idx, user_to_idx,
        genders, ages, occupations, history_window, device, batch_size)
    scores = user_vecs @ item_emb.T
    recs: dict[int, list[int]] = {}
    top_pool = 300
    for row_idx, user_id in enumerate(user_ids):
        seen_idx = [movie_to_idx[i] for i in train_by_user[user_id] if i in movie_to_idx]
        scores[row_idx, seen_idx] = -np.inf
        if scores.shape[1] <= top_pool:
            ranked = np.argsort(-scores[row_idx])
        else:
            top_idx = np.argpartition(-scores[row_idx], top_pool)[:top_pool]
            ranked = top_idx[np.argsort(-scores[row_idx, top_idx])]
        recs[user_id] = [int(movie_ids[idx]) for idx in ranked[:top_pool]]

    rows = evaluate("youtubednn_torch", recs, test_by_user, [20, 50, 100])
    result = pd.DataFrame(rows)
    print()
    print("PyTorch YouTubeDNN evaluation:")
    print(result.round(4))
    if output:
        path = Path(output)
        path.parent.mkdir(parents=True, exist_ok=True)
        result.to_csv(path, index=False, encoding="utf-8-sig")
        print(f"Saved metrics to {path}")
    return result


def save_outputs(
    model: TorchYouTubeDNN,
    out_dir: Path,
    movie_ids: np.ndarray,
    user_ids: np.ndarray,
    vocabs: dict[str, dict[str, int]],
    args: argparse.Namespace,
    min_rating: float,
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    item_emb = model.normalized_item_embeddings()
    np.save(out_dir / "item_emb.npy", item_emb)
    np.save(out_dir / "movie_ids.npy", movie_ids.astype(np.int64))
    torch.save({
        "model_state_dict": model.state_dict(),
        "movie_ids": movie_ids,
        "user_ids": user_ids,
        "vocabs": vocabs,
        "dim": args.dim,
        "hidden_dim": args.hidden_dim,
        "history_window": args.history_window,
    }, out_dir / "youtube_dnn_torch.pt")
    meta = {
        "version": "youtube-torch-v1",
        "trained_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "positive_threshold": float(min_rating),
        "dim": int(args.dim),
        "hidden_dim": int(args.hidden_dim),
        "epochs": int(args.epochs),
        "batch_size": int(args.batch_size),
        "history_window": int(args.history_window),
        "history_cap": int(args.history_cap),
        "max_samples": int(args.max_samples),
    }
    with (out_dir / "youtubednn_torch_meta.json").open("w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    print(f"Wrote {out_dir / 'youtube_dnn_torch.pt'}")
    print(f"Wrote {out_dir / 'item_emb.npy'}")
    print(f"Wrote {out_dir / 'movie_ids.npy'}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", default="scripts/data")
    parser.add_argument("--out-dir", default="data/youtubednn_torch")
    parser.add_argument("--min-rating", default="auto")
    parser.add_argument("--dim", type=int, default=64)
    parser.add_argument("--hidden-dim", type=int, default=128)
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--batch-size", type=int, default=512)
    parser.add_argument("--lr", type=float, default=0.001)
    parser.add_argument("--weight-decay", type=float, default=1e-5)
    parser.add_argument("--dropout", type=float, default=0.1)
    parser.add_argument("--history-window", type=int, default=30)
    parser.add_argument("--history-cap", type=int, default=100)
    parser.add_argument("--max-samples", type=int, default=500000, help="0 means all samples")
    parser.add_argument("--test-ratio", type=float, default=0.2)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--eval-output", default="test-results/youtubednn_torch_eval.csv")
    parser.add_argument("--skip-final-train", action="store_true")
    args = parser.parse_args()

    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)
    device = torch.device("cpu")

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

    print(f"Data dir: {data_dir}")
    print(f"Positive threshold rating >= {min_rating}")
    print(f"Device: {device}")

    _, train_by_user, _, test_by_user = split_by_time(ratings, args.test_ratio, min_rating, 0.0)
    movie_ids, movie_to_idx = build_vocab(movies, train_by_user)
    user_ids, user_to_idx, genders, ages, occupations, vocabs = build_user_tables(users, train_by_user)
    arrays = build_training_arrays(
        train_by_user, movie_to_idx, user_to_idx,
        args.history_window, args.history_cap, args.max_samples, args.seed)
    print(f"Train users: {len(user_ids):,}")
    print(f"Items: {len(movie_ids):,}")
    print(f"Training samples: {len(arrays[0]):,}")

    model = TorchYouTubeDNN(
        num_users=len(user_ids),
        num_items=len(movie_ids),
        gender_size=len(vocabs["gender"]),
        age_size=len(vocabs["age"]),
        occupation_size=len(vocabs["occupation"]),
        dim=args.dim,
        hidden_dim=args.hidden_dim,
        dropout=args.dropout,
        history_window=args.history_window,
    )
    train_model(
        model, arrays, genders, ages, occupations,
        args.epochs, args.batch_size, args.lr, args.weight_decay, device)
    evaluate_model(
        model, train_by_user, test_by_user, movie_ids, movie_to_idx, user_to_idx,
        genders, ages, occupations, args.history_window, device, args.batch_size,
        args.eval_output)

    if args.skip_final_train:
        save_outputs(model, Path(args.out_dir), movie_ids, user_ids, vocabs, args, min_rating)
        return

    print()
    print("Training final model on all positive histories...")
    full_histories = build_histories(ratings, min_rating)
    movie_ids, movie_to_idx = build_vocab(movies, full_histories)
    user_ids, user_to_idx, genders, ages, occupations, vocabs = build_user_tables(users, full_histories)
    arrays = build_training_arrays(
        full_histories, movie_to_idx, user_to_idx,
        args.history_window, args.history_cap, args.max_samples, args.seed)
    final_model = TorchYouTubeDNN(
        num_users=len(user_ids),
        num_items=len(movie_ids),
        gender_size=len(vocabs["gender"]),
        age_size=len(vocabs["age"]),
        occupation_size=len(vocabs["occupation"]),
        dim=args.dim,
        hidden_dim=args.hidden_dim,
        dropout=args.dropout,
        history_window=args.history_window,
    )
    train_model(
        final_model, arrays, genders, ages, occupations,
        args.epochs, args.batch_size, args.lr, args.weight_decay, device)
    save_outputs(final_model, Path(args.out_dir), movie_ids, user_ids, vocabs, args, min_rating)


if __name__ == "__main__":
    main()
