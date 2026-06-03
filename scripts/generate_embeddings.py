"""Generate content-based item embeddings for recall.

Outputs:
  - item_emb.npy:  (N, D) float64 matrix, L2-normalized
  - movie_ids.npy: (N,)  int64 array of movie IDs

The vector is built from movie genres, year, ratings, popularity, and runtime.
It is lightweight enough for a laptop and does not require GPU training.
"""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import psycopg2


PG_DSN = os.environ.get("PG_DSN", "dbname=rec_db user=rec password=rec123 host=localhost port=5432")
OUT_DIR = Path(os.environ.get("OUT_DIR", Path(__file__).resolve().parent.parent / "data"))


def normalize(values: np.ndarray) -> np.ndarray:
    values = values.astype(np.float64)
    finite = np.isfinite(values)
    if not finite.any():
        return np.zeros_like(values, dtype=np.float64)
    fill = np.nanmedian(values[finite])
    values = np.where(finite, values, fill)
    low = values.min()
    high = values.max()
    if high <= low:
        return np.zeros_like(values, dtype=np.float64)
    return (values - low) / (high - low)


def parse_genres(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return [str(v).strip() for v in value if str(v).strip()]
    return [v.strip() for v in str(value).replace("|", ",").split(",") if v.strip()]


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    conn = psycopg2.connect(PG_DSN)
    cur = conn.cursor()
    cur.execute(
        """
        SELECT movie_id, genres, year, avg_rating, rating_count,
               imdb_rating, imdb_votes, runtime_minutes
        FROM movies
        ORDER BY movie_id
        """
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()

    if not rows:
        raise RuntimeError("No movies found. Import data before generating embeddings.")

    movie_ids = np.array([row[0] for row in rows], dtype=np.int64)
    genres_list = [parse_genres(row[1]) for row in rows]
    genre_vocab = sorted({genre for genres in genres_list for genre in genres})
    genre_index = {genre: idx for idx, genre in enumerate(genre_vocab)}

    years = normalize(np.array([np.nan if row[2] is None else row[2] for row in rows], dtype=np.float64))
    avg_ratings = normalize(np.array([np.nan if row[3] is None else row[3] for row in rows], dtype=np.float64))
    rating_counts = normalize(np.log1p(np.array([0 if row[4] is None else row[4] for row in rows], dtype=np.float64)))
    imdb_ratings = normalize(np.array([np.nan if row[5] is None else row[5] for row in rows], dtype=np.float64))
    imdb_votes = normalize(np.log1p(np.array([0 if row[6] is None else row[6] for row in rows], dtype=np.float64)))
    runtimes = normalize(np.array([np.nan if row[7] is None else row[7] for row in rows], dtype=np.float64))

    dim = len(genre_vocab) + 6
    embeddings = np.zeros((len(rows), dim), dtype=np.float64)
    for i, genres in enumerate(genres_list):
        for genre in genres:
            idx = genre_index.get(genre)
            if idx is not None:
                embeddings[i, idx] = 1.0
        base = len(genre_vocab)
        embeddings[i, base] = years[i]
        embeddings[i, base + 1] = avg_ratings[i]
        embeddings[i, base + 2] = rating_counts[i]
        embeddings[i, base + 3] = imdb_ratings[i]
        embeddings[i, base + 4] = imdb_votes[i]
        embeddings[i, base + 5] = runtimes[i]

    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    embeddings = embeddings / np.where(norms == 0, 1.0, norms)

    emb_path = OUT_DIR / "item_emb.npy"
    ids_path = OUT_DIR / "movie_ids.npy"
    np.save(emb_path, embeddings)
    np.save(ids_path, movie_ids)

    print(f"Generated {len(movie_ids)} x {dim} content embeddings -> {emb_path}")
    print(f"Generated {len(movie_ids)} movie IDs                  -> {ids_path}")
    print(f"Genres used: {', '.join(genre_vocab)}")


if __name__ == "__main__":
    main()
