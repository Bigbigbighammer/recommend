"""Generate mock item embeddings for development testing.

Produces two files:
  - item_emb.npy:  (N, D) float64 matrix, L2-normalized
  - movie_ids.npy: (N,)  int64 array of movie IDs

Query PG for the movie IDs, then generate random normalized vectors.
"""

import psycopg2
import numpy as np
import os

PG_DSN = os.environ.get("PG_DSN", "dbname=rec_db user=rec password=rec123 host=localhost port=5432")
OUT_DIR = os.environ.get("OUT_DIR", os.path.join(os.path.dirname(__file__), "..", "data"))
DIM = int(os.environ.get("EMBEDDING_DIM", "16"))
SEED = int(os.environ.get("SEED", "42"))

os.makedirs(OUT_DIR, exist_ok=True)
rng = np.random.default_rng(SEED)

conn = psycopg2.connect(PG_DSN)
cur = conn.cursor()
cur.execute("SELECT movie_id FROM movies ORDER BY movie_id")
movie_ids = np.array([row[0] for row in cur.fetchall()], dtype=np.int64)
cur.close()
conn.close()

N = len(movie_ids)
embeddings = rng.normal(0, 1, (N, DIM)).astype(np.float64)
embeddings = embeddings / np.linalg.norm(embeddings, axis=1, keepdims=True)

emb_path = os.path.join(OUT_DIR, "item_emb.npy")
ids_path = os.path.join(OUT_DIR, "movie_ids.npy")
np.save(emb_path, embeddings)
np.save(ids_path, movie_ids)

print(f"Generated {N} x {DIM} embeddings → {emb_path} ({os.path.getsize(emb_path)} bytes)")
print(f"Generated {N} movie IDs          → {ids_path} ({os.path.getsize(ids_path)} bytes)")
