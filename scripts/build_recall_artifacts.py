"""Build offline recall artifacts for the Java online recall layer.

Outputs under data/ by default:
  - itemcf_sim.csv
  - seqcf_sim.csv
  - ease_sim.csv
  - swing_sim.csv
  - popular_movies.csv

These files are lightweight and can be mounted into the Java service by the
existing docker-compose ./data:/app/data volume.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from offline_recall_eval import (
    build_itemcf,
    build_ease,
    build_seqcf,
    build_movie_popular_scores,
    build_popular,
    build_swing,
    build_usercf,
    load_pickle,
    normalize_columns,
    resolve_data_dir,
)


def build_train_by_user(ratings: pd.DataFrame, min_rating: float) -> dict[int, list[int]]:
    positives = ratings[ratings["rating"] >= min_rating].sort_values(["user_id", "timestamp"])
    return {
        int(user_id): [int(v) for v in group["movie_id"].tolist()]
        for user_id, group in positives.groupby("user_id")
        if len(group) >= 2
    }


def write_similarity(path: Path, sim: dict[int, list[tuple[int, float]]]) -> None:
    rows = []
    for movie_id, related_items in sim.items():
        for rank, (related_movie_id, score) in enumerate(related_items, start=1):
            rows.append((movie_id, related_movie_id, rank, score))
    pd.DataFrame(rows, columns=["movie_id", "related_movie_id", "rank", "score"]).to_csv(
        path, index=False, encoding="utf-8"
    )


def write_user_items(path: Path, train_by_user: dict[int, list[int]]) -> None:
    rows = []
    for user_id, items in train_by_user.items():
        for rank, movie_id in enumerate(reversed(items[-100:]), start=1):
            rows.append((user_id, movie_id, rank))
    pd.DataFrame(rows, columns=["user_id", "movie_id", "rank"]).to_csv(
        path, index=False, encoding="utf-8"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", default="scripts/data")
    parser.add_argument("--out-dir", default="data")
    parser.add_argument("--min-rating", default="auto")
    parser.add_argument("--history-cap", type=int, default=100)
    parser.add_argument("--sim-topn", type=int, default=200)
    parser.add_argument("--seq-window", type=int, default=5)
    parser.add_argument("--ease-reg", type=float, default=500.0)
    parser.add_argument("--swing-alpha", type=float, default=5.0)
    parser.add_argument("--user-topn", type=int, default=80)
    parser.add_argument("--item-user-cap", type=int, default=600)
    args = parser.parse_args()

    data_dir = resolve_data_dir(args.data_dir)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    ratings = normalize_columns(load_pickle(data_dir / "ratings.pkl"))
    ratings["user_id"] = ratings["user_id"].astype(int)
    ratings["movie_id"] = ratings["movie_id"].astype(int)
    ratings["rating"] = ratings["rating"].astype(float)
    if "timestamp" not in ratings.columns:
        ratings["timestamp"] = ratings.groupby("user_id").cumcount()

    if args.min_rating == "auto":
        min_rating = 4.0 if ratings["rating"].max() <= 5 else 8.0
    else:
        min_rating = float(args.min_rating)

    train_by_user = build_train_by_user(ratings, min_rating)
    positives = ratings[ratings["rating"] >= min_rating].copy()

    print(f"Data dir: {data_dir}")
    print(f"Users: {len(train_by_user)}")
    print(f"Positive threshold rating >= {min_rating}")
    print("Building ItemCF similarity...")
    itemcf = build_itemcf(train_by_user, args.history_cap, args.sim_topn)
    write_similarity(out_dir / "itemcf_sim.csv", itemcf)

    print("Building Swing similarity...")
    swing = build_swing(train_by_user, args.history_cap, args.sim_topn, args.swing_alpha)
    write_similarity(out_dir / "swing_sim.csv", swing)

    print("Building SeqCF transition similarity...")
    seqcf = build_seqcf(train_by_user, args.history_cap, args.sim_topn, args.seq_window)
    write_similarity(out_dir / "seqcf_sim.csv", seqcf)

    print("Building EASE similarity...")
    ease = build_ease(train_by_user, args.sim_topn, args.ease_reg)
    write_similarity(out_dir / "ease_sim.csv", ease)

    print("Building UserCF similarity...")
    usercf = build_usercf(train_by_user, args.user_topn, args.item_user_cap)
    write_similarity(out_dir / "usercf_sim.csv", usercf)
    write_user_items(out_dir / "user_positive_items.csv", train_by_user)

    popular = build_popular(positives)
    popular_scores = build_movie_popular_scores(positives)
    pd.DataFrame(
        [(movie_id, rank, popular_scores.get(movie_id, 0.0)) for rank, movie_id in enumerate(popular, start=1)],
        columns=["movie_id", "rank", "score"],
    ).to_csv(out_dir / "popular_movies.csv", index=False, encoding="utf-8")

    print(f"Wrote {out_dir / 'itemcf_sim.csv'}")
    print(f"Wrote {out_dir / 'seqcf_sim.csv'}")
    print(f"Wrote {out_dir / 'ease_sim.csv'}")
    print(f"Wrote {out_dir / 'swing_sim.csv'}")
    print(f"Wrote {out_dir / 'usercf_sim.csv'}")
    print(f"Wrote {out_dir / 'user_positive_items.csv'}")
    print(f"Wrote {out_dir / 'popular_movies.csv'}")


if __name__ == "__main__":
    main()
