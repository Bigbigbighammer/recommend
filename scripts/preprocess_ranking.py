"""Ranking data preprocessing: build training samples for DeepFM CTR model.

Reads ratings/users/movies from PostgreSQL, encodes categorical features,
generates positive/negative samples, splits by user and timestamp.

Usage:
    python scripts/preprocess_ranking.py [--output-dir PATH] [--neg-ratio 4]
"""

import argparse
import os
import pickle
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
import psycopg2
from sklearn.preprocessing import LabelEncoder

PG_DSN = os.environ.get("PG_DSN", "dbname=rec_db user=rec password=rec123 host=localhost port=5432")
DEFAULT_OUT = Path(__file__).resolve().parent / "output_ranking"
SEED = 42

# ── Feature column definitions ───────────────────────────────────────
# These must match what the Java side sends in RankingRequest.

USER_FEATURES = ["user_id", "gender", "age", "occupation", "zip_code",
                "user_avg_rating_bin", "user_rating_count_bin", "user_active_days_bin"]
ITEM_FEATURES = ["movie_id", "genres", "is_adult", "year", "avg_rating_bin",
                "rating_count_bin", "rating_deviation_bin",
                "imdb_rating_bin", "imdb_votes_bin"]
LABEL_COL = "click"


def _safe_int(v):
    """Convert value to int, treating NaN/None as 0."""
    if v is None:
        return 0
    try:
        return int(v)
    except (ValueError, TypeError):
        return 0


def _safe_float(v):
    """Convert value to float, treating NaN/None as 0.0."""
    if v is None:
        return 0.0
    try:
        return float(v)
    except (ValueError, TypeError):
        return 0.0


def bin_year(y):
    """Bin release year into decade categories."""
    if y is None or y == 0:
        return "Unknown"
    y = int(y)
    if y < 1950:
        return "pre-1950"
    decade = (y // 10) * 10
    return f"{decade}s"


def bin_avg_rating(v):
    """Bin avg_rating (1-10) into 0.5-width buckets."""
    if v is None or v <= 0:
        return "Unknown"
    bucket = round(float(v) * 2) / 2
    return f"{bucket:.1f}"


def bin_rating_count(v):
    """Bin rating_count into log-scale buckets."""
    if v is None or v < 0:
        return "Unknown"
    v = int(v)
    if v == 0:
        return "0"
    if v <= 5:
        return "1-5"
    if v <= 20:
        return "6-20"
    if v <= 50:
        return "21-50"
    if v <= 100:
        return "51-100"
    if v <= 200:
        return "101-200"
    if v <= 500:
        return "201-500"
    return "501+"


def bin_active_days(v):
    """Bin user active days into buckets."""
    if v is None or v < 0:
        return "Unknown"
    v = int(v)
    if v == 0:
        return "0"
    if v <= 7:
        return "1-7"
    if v <= 30:
        return "8-30"
    if v <= 90:
        return "31-90"
    if v <= 180:
        return "91-180"
    if v <= 365:
        return "181-365"
    return "365+"


def bin_rating_deviation(v):
    """Bin rating deviation (user_avg - movie_avg) into 0.5-width buckets, including negative."""
    if v is None:
        return "Unknown"
    bucket = round(float(v) * 2) / 2
    return f"{bucket:.1f}"


def bin_imdb_votes(v):
    """Bin imdb_votes into log-scale buckets."""
    if v is None or v <= 0:
        return "Unknown"
    v = int(v)
    if v <= 100:
        return "1-100"
    if v <= 1000:
        return "101-1K"
    if v <= 10000:
        return "1K-10K"
    if v <= 100000:
        return "10K-100K"
    if v <= 500000:
        return "100K-500K"
    return "500K+"


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def load_data(pg_dsn):
    """Load ratings, users, movies from PG into DataFrames."""
    log("Loading data from PostgreSQL ...")
    conn = psycopg2.connect(pg_dsn)

    ratings = pd.read_sql("SELECT user_id, movie_id, rating, timestamp FROM ratings", conn)
    log(f"  ratings: {len(ratings):,}")

    users = pd.read_sql("SELECT user_id, gender, age, occupation, zip_code FROM users", conn)
    log(f"  users:   {len(users):,}")

    movies = pd.read_sql("SELECT movie_id, genres, is_adult, year, avg_rating, rating_count, "
                         "imdb_rating, imdb_votes FROM movies", conn)
    log(f"  movies:  {len(movies):,}")

    conn.close()
    return ratings, users, movies


def prepare_samples(ratings, users, movies, neg_ratio=4, pos_threshold=4.0, relative_threshold=False):
    """Build positive and negative samples with merged features.

    Positive: rating >= pos_threshold
    Negative: randomly sampled from unrated movies (neg_ratio per positive)
    """
    rng = np.random.default_rng(SEED)
    log(f"Preparing samples (pos_threshold={pos_threshold}, neg_ratio={neg_ratio}) ...")

    # Merge ratings with user and movie features
    merged = ratings.merge(users, on="user_id", how="left")
    merged = merged.merge(movies, on="movie_id", how="left")

    # Extract first genre as scalar (DeepFM requires scalar features)
    merged["genres"] = merged["genres"].apply(
        lambda g: g[0] if isinstance(g, list) and len(g) > 0 else "Unknown"
    )

    # Compute per-user statistics from ratings
    log("Computing user statistics ...")
    user_stats = ratings.groupby("user_id").agg(
        user_avg_rating=("rating", "mean"),
        user_rating_count=("rating", "count"),
        user_max_ts=("timestamp", "max"),
        user_min_ts=("timestamp", "min"),
    ).reset_index()
    user_stats["user_active_days"] = (
        (user_stats["user_max_ts"] - user_stats["user_min_ts"]) / 86400.0
    ).clip(lower=0)

    # Bin user stats
    user_stats["user_avg_rating_bin"] = user_stats["user_avg_rating"].apply(bin_avg_rating)
    user_stats["user_rating_count_bin"] = user_stats["user_rating_count"].apply(bin_rating_count)
    user_stats["user_active_days_bin"] = user_stats["user_active_days"].apply(bin_active_days)

    # Keep binned columns + raw user_avg_rating for deviation computation
    user_stats_binned = user_stats[["user_id", "user_avg_rating_bin",
                                     "user_rating_count_bin", "user_active_days_bin",
                                     "user_avg_rating"]]
    merged = merged.merge(user_stats_binned, on="user_id", how="left")

    # Compute rating deviation: user_avg - movie_avg
    merged["rating_deviation"] = merged["user_avg_rating"] - merged["avg_rating"]
    merged["rating_deviation_bin"] = merged["rating_deviation"].apply(bin_rating_deviation)
    merged.drop(columns=["rating_deviation"], inplace=True)
    # Keep user_avg_rating (raw) for neg_sample deviation computation;
    # will be dropped during encode_features (not a feature column)
    log(f"  User stats merged: {len(user_stats_binned):,} users, rating_deviation computed")

    # Apply binning to continuous item features
    merged["year"] = merged["year"].apply(lambda y: bin_year(y))
    merged["avg_rating_bin"] = merged["avg_rating"].apply(lambda v: bin_avg_rating(v))
    merged["rating_count_bin"] = merged["rating_count"].apply(lambda v: bin_rating_count(v))
    merged["imdb_rating_bin"] = merged["imdb_rating"].apply(
        lambda v: bin_avg_rating(v) if not pd.isna(v) else "Unknown")
    merged["imdb_votes_bin"] = merged["imdb_votes"].apply(
        lambda v: bin_imdb_votes(v) if not pd.isna(v) else "Unknown")

    # Label: positive = rating >= threshold (absolute or relative to user mean)
    if relative_threshold:
        user_avg = ratings.groupby("user_id")["rating"].mean().reset_index()
        user_avg.columns = ["user_id", "_user_threshold"]
        merged = merged.merge(user_avg, on="user_id", how="left")
        merged[LABEL_COL] = (merged["rating"] >= merged["_user_threshold"]).astype(int)
        merged.drop(columns=["_user_threshold"], inplace=True)
        log("  Using relative threshold (rating >= user's mean rating)")
    else:
        merged[LABEL_COL] = (merged["rating"] >= pos_threshold).astype(int)

    n_pos = merged[LABEL_COL].sum()
    n_neg = len(merged) - n_pos
    log(f"  All ratings: {len(merged):,} (positive={n_pos:,}, negative={n_neg:,})")

    # Build user → rated movies index for negative sampling
    user_rated = defaultdict(set)
    all_movie_ids = set(movies["movie_id"].tolist())
    all_users = set(users["user_id"].tolist())

    for _, row in ratings.iterrows():
        user_rated[int(row["user_id"])].add(int(row["movie_id"]))

    # Split users: 80% train, 10% val, 10% test
    user_list = sorted(all_users)
    rng.shuffle(user_list)
    n_train = int(len(user_list) * 0.8)
    n_val = int(len(user_list) * 0.1)

    train_users = set(user_list[:n_train])
    val_users = set(user_list[n_train:n_train + n_val])
    test_users = set(user_list[n_train + n_val:])

    log(f"  Split: train_user={len(train_users)}, val_user={len(val_users)}, test_user={len(test_users)}")

    # Split merged data by user
    train_data = merged[merged["user_id"].isin(train_users)]
    val_data = merged[merged["user_id"].isin(val_users)]
    test_data = merged[merged["user_id"].isin(test_users)]

    def _build_split(df, user_set, desc):
        """Build positive + negative samples for one split."""
        pos = df[df[LABEL_COL] == 1].copy()
        neg_existing = df[df[LABEL_COL] == 0].copy()

        # Pre-build movie lookup dict for O(1) access
        movie_lookup = {}
        for _, mr in movies.iterrows():
            movie_lookup[int(mr["movie_id"])] = mr

        # Pre-build candidate array per user
        all_movie_arr = np.array(sorted(all_movie_ids), dtype=np.int64)

        # Sample negative from unrated movies
        neg_samples = []
        for _, row in pos.iterrows():
            uid = int(row["user_id"])
            rated = user_rated[uid]
            # Use numpy setdiff for fast candidate computation
            candidates = np.setdiff1d(all_movie_arr, np.array(sorted(rated), dtype=np.int64))
            if len(candidates) < neg_ratio:
                candidates = np.setdiff1d(all_movie_arr, np.array([int(row["movie_id"])], dtype=np.int64))
            if len(candidates) == 0:
                continue
            sampled = rng.choice(candidates, size=min(neg_ratio, len(candidates)), replace=False)
            for mid in sampled:
                mr = movie_lookup[int(mid)]
                # Compute cross feature for this negative sample
                mr_genres = mr["genres"]
                mr_genres_list = mr_genres if isinstance(mr_genres, list) else []
                user_avg_raw = row.get("user_avg_rating", 0) or 0
                deviation = float(user_avg_raw) - float(mr["avg_rating"] or 0)

                neg_samples.append({
                    "user_id": uid,
                    "movie_id": int(mid),
                    "rating": 0,
                    "timestamp": int(row["timestamp"]),
                    "gender": row["gender"],
                    "age": row["age"],
                    "occupation": row["occupation"],
                    "zip_code": row["zip_code"],
                    "user_avg_rating_bin": row["user_avg_rating_bin"],
                    "user_rating_count_bin": row["user_rating_count_bin"],
                    "user_active_days_bin": row["user_active_days_bin"],
                    "genres": mr_genres_list[0] if len(mr_genres_list) > 0 else "Unknown",
                    "is_adult": _safe_int(mr["is_adult"]),
                    "year": bin_year(mr["year"]),
                    "avg_rating_bin": bin_avg_rating(mr["avg_rating"]),
                    "rating_count_bin": bin_rating_count(mr["rating_count"]),
                    "rating_deviation_bin": bin_rating_deviation(deviation),
                    "imdb_rating_bin": bin_avg_rating(mr["imdb_rating"])
                        if not pd.isna(mr.get("imdb_rating")) else "Unknown",
                    "imdb_votes_bin": bin_imdb_votes(mr["imdb_votes"])
                        if not pd.isna(mr.get("imdb_votes")) else "Unknown",
                    LABEL_COL: 0,
                })

        neg_df = pd.DataFrame(neg_samples)
        result = pd.concat([pos, neg_existing, neg_df], ignore_index=True)
        log(f"  {desc}: pos={len(pos):,}, neg_existing={len(neg_existing):,}, neg_sampled={len(neg_df):,}")
        return result

    train_final = _build_split(train_data, train_users, "train")
    val_final = _build_split(val_data, val_users, "val")
    test_final = _build_split(test_data, test_users, "test")

    return train_final, val_final, test_final, train_users, val_users, test_users


def encode_features(train_df, val_df, test_df):
    """Label-encode all categorical features. Save encoders.

    Returns (train_encoded, val_encoded, test_encoded, encoders_dict)
    where each encoded is a dict of numpy arrays.
    """
    log("Encoding features ...")

    all_features = USER_FEATURES + ITEM_FEATURES
    encoders = {}

    # Fit encoders on train only
    for feat in all_features:
        le = LabelEncoder()
        # Collect all values including unknown placeholder
        train_vals = train_df[feat].fillna("Unknown").astype(str).tolist()
        le.fit(list(set(train_vals)))
        encoders[feat] = le
        log(f"  {feat}: {len(le.classes_)} classes")

    def _transform(df):
        result = {}
        for feat in all_features:
            le = encoders[feat]
            vals = df[feat].fillna("Unknown").astype(str).values
            known_mask = np.isin(vals, le.classes_)
            encoded = np.zeros(len(vals), dtype=np.int64)
            if known_mask.any():
                encoded[known_mask] = le.transform(vals[known_mask])
            result[feat] = encoded
        # Keep original user_id for per-user metric grouping
        result["orig_user_id"] = df["user_id"].fillna(0).astype(np.int64).values
        result[LABEL_COL] = df[LABEL_COL].values.astype(np.float32)
        return result

    train_enc = _transform(train_df)
    val_enc = _transform(val_df)
    test_enc = _transform(test_df)

    return train_enc, val_enc, test_enc, encoders


def save_output(train, val, test, encoders, feature_dims, output_dir):
    """Save processed data as npz files and encoders as pickle."""
    os.makedirs(output_dir, exist_ok=True)

    log(f"Saving to {output_dir} ...")

    for name, data in [("train", train), ("val", val), ("test", test)]:
        path = os.path.join(output_dir, f"{name}_ranking.npz")
        np.savez_compressed(path, **data)
        n = len(data[LABEL_COL])
        log(f"  {path}  ({n:,} samples)")

    # Save encoders
    enc_path = os.path.join(output_dir, "ranking_encoders.pkl")
    with open(enc_path, "wb") as f:
        pickle.dump(encoders, f)
    log(f"  {enc_path}")

    # Save feature dimensions
    dims_path = os.path.join(output_dir, "ranking_feature_dims.pkl")
    with open(dims_path, "wb") as f:
        pickle.dump(feature_dims, f)
    log(f"  {dims_path}")

    # Also save to inference-service model_weights directory
    infer_dir = Path(__file__).resolve().parent.parent / "inference-service" / "model_weights"
    os.makedirs(infer_dir, exist_ok=True)
    infer_enc_path = infer_dir / "ranking_encoders.pkl"
    infer_dims_path = infer_dir / "ranking_feature_dims.pkl"
    with open(infer_enc_path, "wb") as f:
        pickle.dump(encoders, f)
    with open(infer_dims_path, "wb") as f:
        pickle.dump(feature_dims, f)
    log(f"  Copied encoders → {infer_enc_path}")
    log(f"  Copied dims     → {infer_dims_path}")


def main():
    parser = argparse.ArgumentParser(description="Preprocess ranking data for DeepFM training")
    parser.add_argument("--output-dir", type=str, default=str(DEFAULT_OUT))
    parser.add_argument("--neg-ratio", type=int, default=4, help="Negative samples per positive")
    parser.add_argument("--pos-threshold", type=float, default=4.0, help="Rating >= threshold = positive")
    parser.add_argument("--relative-threshold", action="store_true", default=False,
                        help="Use rating >= user_avg_rating as positive label instead of absolute threshold")
    args = parser.parse_args()

    t0 = time.time()
    rng = np.random.default_rng(SEED)
    np.random.seed(SEED)

    ratings, users, movies = load_data(PG_DSN)

    train_df, val_df, test_df, train_users, val_users, test_users = prepare_samples(
        ratings, users, movies, neg_ratio=args.neg_ratio,
        pos_threshold=args.pos_threshold, relative_threshold=args.relative_threshold
    )

    train_enc, val_enc, test_enc, encoders = encode_features(train_df, val_df, test_df)

    # Build feature dimension dict for model construction
    all_features = USER_FEATURES + ITEM_FEATURES
    feature_dims = {}
    for feat in all_features:
        feature_dims[feat] = len(encoders[feat].classes_)
    feature_dims["num_user_features"] = len(USER_FEATURES)
    feature_dims["num_item_features"] = len(ITEM_FEATURES)
    feature_dims["user_features"] = USER_FEATURES
    feature_dims["item_features"] = ITEM_FEATURES
    feature_dims["all_features"] = all_features

    save_output(train_enc, val_enc, test_enc, encoders, feature_dims, args.output_dir)

    log(f"DONE in {(time.time() - t0) / 60:.1f} min")


if __name__ == "__main__":
    main()
