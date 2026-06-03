"""Import MovieLens 1M + IMDb data from pickle files into PostgreSQL, ES, and Redis.

Data source: scripts/data/{movies,users,ratings}.pkl + movie_metadata.pkl + image.zip

Usage:
    python scripts/ingest_data.py [--data-dir PATH] [--skip-ratings] [--create-test-user]
"""

import argparse
import os
import pickle
import re
import sys
import time
from pathlib import Path

import pandas as pd
import psycopg2
from psycopg2.extras import execute_values

PG_DSN = os.environ.get("PG_DSN", "dbname=rec_db user=rec password=rec123 host=localhost port=5432")
DEFAULT_DATA_DIR = Path(__file__).resolve().parent / "data"
BATCH = 5000


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


# ── helpers ────────────────────────────────────────────────────────

def clean_title(t):
    """Strip parenthetical year from title: 'Toy Story (1995)' -> 'Toy Story'"""
    return re.sub(r'\s*\(\d{4}\)\s*$', '', str(t)).strip()


def extract_year(t):
    """Extract year from title: 'Toy Story (1995)' -> 1995"""
    m = re.search(r'\((\d{4})\)\s*$', str(t))
    return int(m.group(1)) if m else None


def _null(v):
    """Convert NaN/'\\N' to None."""
    if v is None or (isinstance(v, float) and pd.isna(v)) or str(v) == '\\N':
        return None
    return v


def _int(v):
    v = _null(v)
    return int(v) if v is not None else None


def _float(v):
    v = _null(v)
    return float(v) if v is not None else None


def _str(v):
    v = _null(v)
    return str(v).replace("'", "''") if v is not None else None


def _genres(v):
    """Convert pipe-separated genres to PG array literal."""
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    genres = [g.strip().replace("'", "''") for g in str(v).split('|') if g.strip()]
    return "{" + ",".join(genres) + "}" if genres else None


def _pg_array(v):
    """Comma-separated string → PG array literal."""
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    items = [x.strip() for x in str(v).split(',') if x.strip() and x.strip() != '\\N']
    return "{" + ",".join(items) + "}" if items else None


# ── import functions ───────────────────────────────────────────────

def import_movies(conn, df):
    log(f"Importing {len(df):,} movies ...")
    cur = conn.cursor()
    batch, count = [], 0
    for _, row in df.iterrows():
        batch.append((
            int(row['movie_id']),
            _str(row.get('imdb_id')),
            clean_title(row['title']),
            extract_year(row['title']),
            _genres(row.get('genres')),
            _str(row.get('description')),
            _str(row.get('titleType')),
            _int(row.get('runtimeMinutes')),
            _int(row.get('isAdult')),
            _float(row.get('averageRating')),
            _int(row.get('numVotes')),
            f"/posters/{int(row['movie_id'])}.png",
        ))
        count += 1
        if len(batch) >= BATCH:
            _flush_movies(cur, batch); batch.clear()
    if batch:
        _flush_movies(cur, batch)
    conn.commit(); cur.close()
    log(f"Movies: {count:,} imported")


def _flush_movies(cur, batch):
    execute_values(cur, """INSERT INTO movies
        (movie_id, imdb_id, title, year, genres, description, title_type, runtime_minutes, is_adult, imdb_rating, imdb_votes, poster_url, avg_rating, rating_count)
        VALUES %s ON CONFLICT (movie_id) DO UPDATE SET
        imdb_id=EXCLUDED.imdb_id, title=EXCLUDED.title, year=EXCLUDED.year,
        genres=EXCLUDED.genres, description=EXCLUDED.description,
        title_type=EXCLUDED.title_type, runtime_minutes=EXCLUDED.runtime_minutes,
        is_adult=EXCLUDED.is_adult, imdb_rating=EXCLUDED.imdb_rating,
        imdb_votes=EXCLUDED.imdb_votes, poster_url=EXCLUDED.poster_url""",
        batch, template="(%s,%s,%s,%s,%s::text[],%s,%s,%s,%s,%s,%s,%s,0,0)")


def import_users(conn, df):
    log(f"Importing {len(df):,} users ...")
    cur = conn.cursor()
    batch, count, max_id = [], 0, 0
    for _, row in df.iterrows():
        uid = int(row['user_id'])
        max_id = max(max_id, uid)
        batch.append((
            uid,
            f"u{uid}@rec.dev",
            f"user{uid}",
            "pw",
            _str(row.get('gender')),
            str(row.get('age', '')),
            str(row.get('occupation', '')),
            str(row.get('zip_code', '')),
        ))
        count += 1
        if len(batch) >= BATCH:
            _flush_users(cur, batch); batch.clear()
    if batch:
        _flush_users(cur, batch)
    # Reset sequence
    cur.execute(f"SELECT setval('users_user_id_seq', {max_id + 1})")
    conn.commit(); cur.close()
    log(f"Users: {count:,} imported, sequence reset to {max_id + 1}")


def _flush_users(cur, batch):
    execute_values(cur, """INSERT INTO users
        (user_id, email, username, hashed_password, is_active, gender, age, occupation, zip_code)
        VALUES %s ON CONFLICT (user_id) DO NOTHING""",
        batch, template="(%s,%s,%s,%s,1,%s,%s,%s,%s)")


def import_ratings(conn, df):
    log(f"Importing {len(df):,} ratings ...")
    cur = conn.cursor()
    batch, count = [], 0
    for _, row in df.iterrows():
        batch.append((
            int(row['user_id']), int(row['movie_id']),
            float(row['rating']), int(row['timestamp']),
        ))
        count += 1
        if len(batch) >= BATCH:
            _flush_ratings(cur, batch); batch.clear()
            log(f"  {count:,} rows ...")
    if batch:
        _flush_ratings(cur, batch)
    conn.commit(); cur.close()
    log(f"Ratings: {count:,} imported")


def _flush_ratings(cur, batch):
    execute_values(cur, """INSERT INTO ratings (user_id, movie_id, rating, timestamp)
        VALUES %s ON CONFLICT (user_id, movie_id) DO NOTHING""",
        batch, template="(%s,%s,%s,%s)")


def update_movie_stats(conn):
    log("Updating movie statistics from ratings ...")
    cur = conn.cursor()
    cur.execute("""UPDATE movies m SET avg_rating = r.avg_rating, rating_count = r.rating_count
        FROM (SELECT movie_id, AVG(rating)::FLOAT as avg_rating, COUNT(*)::INTEGER as rating_count
              FROM ratings GROUP BY movie_id) r
        WHERE m.movie_id = r.movie_id""")
    updated = cur.rowcount
    cur.execute("SELECT setval('movies_movie_id_seq', COALESCE((SELECT MAX(movie_id) FROM movies), 1))")
    conn.commit(); cur.close()
    log(f"Stats updated for {updated} movies")


def import_metadata(conn, data_dir):
    path = data_dir / "movie_metadata.pkl"
    log(f"Loading metadata from {path} ...")
    with open(path, 'rb') as f:
        meta = pickle.load(f)

    for table, df in meta.items():
        log(f"  Importing {table}: {len(df):,} rows ...")
        cur = conn.cursor()
        cur.execute(f"TRUNCATE {table}")
        conn.commit()
        batch, count = [], 0

        for _, row in df.iterrows():
            if table == 'title_ratings':
                batch.append((row['tconst'], float(row['averageRating']), int(row['numVotes'])))
                if len(batch) >= BATCH:
                    execute_values(cur, "INSERT INTO title_ratings (tconst,average_rating,num_votes) VALUES %s", batch, template="(%s,%s,%s)")
                    conn.commit(); batch.clear()
            elif table == 'name_basics':
                batch.append((
                    row['nconst'], _str(row['primaryName']),
                    _int(row.get('birthYear')), _int(row.get('deathYear')),
                    _pg_array(row.get('primaryProfession')),
                    _pg_array(row.get('knownForTitles')),
                ))
                if len(batch) >= BATCH:
                    execute_values(cur, "INSERT INTO name_basics (nconst,primary_name,birth_year,death_year,primary_profession,known_for_titles) VALUES %s", batch, template="(%s,%s,%s,%s,%s::text[],%s::text[])")
                    conn.commit(); batch.clear()
            elif table == 'title_crew':
                batch.append((row['tconst'], _pg_array(row.get('directors')), _pg_array(row.get('writers'))))
                if len(batch) >= BATCH:
                    execute_values(cur, "INSERT INTO title_crew (tconst,directors,writers) VALUES %s", batch, template="(%s,%s::text[],%s::text[])")
                    conn.commit(); batch.clear()
            elif table == 'title_principals':
                batch.append((
                    row['tconst'], int(row['ordering']), row['nconst'],
                    _str(row.get('category')), _str(row.get('job')), _str(row.get('characters')),
                ))
                if len(batch) >= BATCH:
                    execute_values(cur, "INSERT INTO title_principals (tconst,ordering,nconst,category,job,characters) VALUES %s", batch, template="(%s,%s,%s,%s,%s,%s)")
                    conn.commit(); batch.clear()
            elif table == 'title_akas':
                batch.append((
                    row['tconst'], int(row['ordering']), _str(row['title']),
                    _str(row.get('region')), _str(row.get('language')),
                    _str(row.get('types')), _str(row.get('attributes')),
                    int(row.get('isOriginalTitle', 0)) if _null(row.get('isOriginalTitle')) else 0,
                ))
                if len(batch) >= BATCH:
                    execute_values(cur, "INSERT INTO title_akas (tconst,ordering,title,region,language,types,attributes,is_original_title) VALUES %s", batch, template="(%s,%s,%s,%s,%s,%s,%s,%s)")
                    conn.commit(); batch.clear()
            count += 1

        if batch:
            templates = {
                'title_ratings': "(%s,%s,%s)",
                'name_basics': "(%s,%s,%s,%s,%s::text[],%s::text[])",
                'title_crew': "(%s,%s::text[],%s::text[])",
                'title_principals': "(%s,%s,%s,%s,%s,%s)",
                'title_akas': "(%s,%s,%s,%s,%s,%s,%s,%s)",
            }
            cols = {
                'title_ratings': "tconst,average_rating,num_votes",
                'name_basics': "nconst,primary_name,birth_year,death_year,primary_profession,known_for_titles",
                'title_crew': "tconst,directors,writers",
                'title_principals': "tconst,ordering,nconst,category,job,characters",
                'title_akas': "tconst,ordering,title,region,language,types,attributes,is_original_title",
            }
            execute_values(cur, f"INSERT INTO {table} ({cols[table]}) VALUES %s", batch, template=templates[table])
            conn.commit()
        cur.close()
        log(f"    {table}: {count:,} rows")


def import_genres(conn, df_movies):
    log("Importing genres ...")
    all_genres = set()
    for g in df_movies['genres']:
        if g and (isinstance(g, str)):
            for genre in g.split('|'):
                genre = genre.strip()
                if genre and genre != '(no genres listed)':
                    all_genres.add(genre.replace("'", "''"))
    cur = conn.cursor()
    for name in sorted(all_genres):
        cur.execute("INSERT INTO genres (name) VALUES (%s) ON CONFLICT (name) DO NOTHING", (name,))
    conn.commit(); cur.close()
    log(f"Genres: {len(all_genres)} imported")


def copy_posters(data_dir):
    """Copy poster images from image/ directory to a location nginx can serve."""
    src = data_dir / "image"
    dst = Path(__file__).resolve().parent.parent / "data" / "posters"
    dst.mkdir(parents=True, exist_ok=True)
    count = 0
    for img in src.glob("*.png"):
        target = dst / img.name
        if not target.exists():
            target.write_bytes(img.read_bytes())
        count += 1
    log(f"Posters: {count} copied to {dst}")


def create_test_user(conn):
    log("Creating test user ...")
    email, password = "test@rec.dev", "test123456"
    cur = conn.cursor()
    cur.execute("SELECT user_id FROM users WHERE email = %s", (email,))
    if cur.fetchone():
        log(f"  User {email} already exists")
        cur.close()
        return
    cur.execute("""INSERT INTO users (email, username, hashed_password, is_active, is_superuser, gender, age, occupation, preferred_genres)
        VALUES (%s,%s,%s,1,1,'M','25','Engineer','{Sci-Fi}')""",
        (email, email, password))
    conn.commit(); cur.close()
    log(f"  Created {email} / {password}")


# ── Elasticsearch ───────────────────────────────────────────────────

def index_es(conn):
    """Index movies from PG into Elasticsearch using direct HTTP."""
    import json, urllib.request

    ES_URL = os.environ.get("ES_URL", "http://localhost:9200")
    log(f"Indexing movies into Elasticsearch at {ES_URL} ...")

    # Delete existing index
    req = urllib.request.Request(f"{ES_URL}/movies", method="DELETE")
    try: urllib.request.urlopen(req)
    except: pass

    # Create index with mapping
    mapping = {
        "mappings": {
            "properties": {
                "movieId": {"type": "long"},
                "title": {"type": "text"},
                "year": {"type": "integer"},
                "genres": {"type": "keyword"},
                "description": {"type": "text"},
                "avgRating": {"type": "float"},
                "ratingCount": {"type": "integer"},
                "imdbRating": {"type": "float"},
                "imdbVotes": {"type": "integer"},
            }
        }
    }
    req = urllib.request.Request(f"{ES_URL}/movies", data=json.dumps(mapping).encode(),
        headers={"Content-Type": "application/json"}, method="PUT")
    urllib.request.urlopen(req)

    # Bulk index
    cur = conn.cursor()
    cur.execute("SELECT movie_id, title, year, genres, description, avg_rating, rating_count, imdb_rating, imdb_votes FROM movies")
    batch, count = [], 0
    for row in cur.fetchall():
        action = json.dumps({"index": {"_id": str(row[0])}})
        doc = json.dumps({
            "movieId": row[0], "title": row[1], "year": row[2],
            "genres": row[3] if isinstance(row[3], list) else [],
            "description": row[4] or "", "avgRating": row[5] or 0,
            "ratingCount": row[6] or 0, "imdbRating": row[7], "imdbVotes": row[8],
        })
        batch.append(action + "\n" + doc)
        count += 1
        if len(batch) >= 500:
            body = "\n".join(batch) + "\n"
            req = urllib.request.Request(f"{ES_URL}/movies/_bulk", data=body.encode(),
                headers={"Content-Type": "application/x-ndjson"}, method="POST")
            urllib.request.urlopen(req)
            batch.clear()
            log(f"  {count:,} / {cur.rowcount:,} indexed ...")
    if batch:
        body = "\n".join(batch) + "\n"
        req = urllib.request.Request(f"{ES_URL}/movies/_bulk", data=body.encode(),
            headers={"Content-Type": "application/x-ndjson"}, method="POST")
        urllib.request.urlopen(req)
    cur.close()
    log(f"ES: {count:,} movies indexed")


# ── Redis ───────────────────────────────────────────────────────────

def populate_redis(conn):
    """Populate Redis with user profiles and history from PG."""
    import redis as redis_py
    from collections import Counter

    REDIS_HOST = os.environ.get("REDIS_HOST", "localhost")
    r = redis_py.Redis(host=REDIS_HOST, port=6379, decode_responses=True)
    log(f"Populating Redis at {REDIS_HOST} ...")

    cur = conn.cursor()

    # User profiles
    cur.execute("SELECT user_id, gender, age, occupation, zip_code FROM users")
    pipe = r.pipeline()
    count = 0
    for uid, gender, age, occ, zipc in cur.fetchall():
        key = f"user:{uid}:profile"
        mapping = {}
        if gender: mapping['gender'] = gender
        if age: mapping['age'] = age
        if occ: mapping['occupation'] = occ
        if zipc: mapping['zipCode'] = zipc
        if mapping:
            pipe.hset(key, mapping=mapping)
        count += 1
        if count % 500 == 0:
            pipe.execute()
    pipe.execute()
    log(f"  {count:,} user profiles")

    # User history (movie_ids by rating timestamp)
    cur.execute("SELECT user_id, movie_id FROM ratings ORDER BY user_id, timestamp")
    pipe = r.pipeline()
    count, current_uid = 0, None
    for uid, mid in cur.fetchall():
        if uid != current_uid:
            current_uid = uid
        key = f"user:{uid}:history"
        pipe.rpush(key, str(mid))
        count += 1
        if count % 5000 == 0:
            pipe.execute()
    pipe.execute()
    log(f"  {count:,} history entries")

    # Frequent genres per user
    cur.execute("""
        SELECT r.user_id, m.genres FROM ratings r
        JOIN movies m ON r.movie_id = m.movie_id ORDER BY r.user_id
    """)
    pipe = r.pipeline()
    count, current_uid, genre_counter = 0, None, Counter()
    for uid, genres in cur.fetchall():
        if uid != current_uid:
            if current_uid is not None and genre_counter:
                top3 = [g for g, _ in genre_counter.most_common(3)]
                pipe.hset(f"user:{current_uid}:profile", "frequent_genres", ",".join(top3))
            current_uid = uid
            genre_counter = Counter()
        if genres:
            genre_counter.update(genres)
        count += 1
    if current_uid is not None and genre_counter:
        top3 = [g for g, _ in genre_counter.most_common(3)]
        pipe.hset(f"user:{current_uid}:profile", "frequent_genres", ",".join(top3))
    pipe.execute()
    log(f"  Frequent genres computed for users")

    cur.close()


# ── verify ──────────────────────────────────────────────────────────

def verify(conn):
    cur = conn.cursor()
    tables = ["users", "movies", "ratings", "genres",
              "title_ratings", "name_basics", "title_crew",
              "title_principals", "title_akas"]
    print("\n=== Import Summary ===")
    for t in tables:
        cur.execute(f"SELECT count(*) FROM {t}")
        print(f"  {t:25s}: {cur.fetchone()[0]:>10,}")
    cur.execute("SELECT count(*) FROM movies WHERE imdb_id IS NOT NULL")
    print(f"  {'movies with imdb_id':25s}: {cur.fetchone()[0]:>10,}")
    cur.execute("SELECT count(*) FROM movies WHERE imdb_rating IS NOT NULL")
    print(f"  {'movies with imdb_rating':25s}: {cur.fetchone()[0]:>10,}")
    cur.close()


# ── main ────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Import MovieLens+IMDb data into PostgreSQL/ES/Redis")
    parser.add_argument("--data-dir", type=str, default=str(DEFAULT_DATA_DIR))
    parser.add_argument("--skip-ratings", action="store_true")
    parser.add_argument("--create-test-user", action="store_true")
    parser.add_argument("--skip-es", action="store_true")
    parser.add_argument("--skip-redis", action="store_true")
    parser.add_argument("--skip-posters", action="store_true")
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    t0 = time.time()

    log(f"=== Importing from {data_dir} ===")

    # Load pickle files
    log("Loading pickle files ...")
    df_movies = pd.read_pickle(str(data_dir / "movies.pkl"))
    df_users = pd.read_pickle(str(data_dir / "users.pkl"))
    df_ratings = pd.read_pickle(str(data_dir / "ratings.pkl"))
    log(f"  movies={len(df_movies):,}  users={len(df_users):,}  ratings={len(df_ratings):,}")

    # Connect to PG
    conn = psycopg2.connect(PG_DSN)

    # Import in dependency order
    log("=== Step 1: Movies ===")
    import_movies(conn, df_movies)

    log("=== Step 2: Users ===")
    import_users(conn, df_users)

    log("=== Step 3: Ratings ===")
    if not args.skip_ratings:
        import_ratings(conn, df_ratings)
        update_movie_stats(conn)

    log("=== Step 4: IMDb Metadata ===")
    import_metadata(conn, data_dir)

    log("=== Step 5: Genres ===")
    import_genres(conn, df_movies)

    if args.create_test_user:
        create_test_user(conn)

    conn.close()

    # Posters
    if not args.skip_posters:
        log("=== Step 6: Posters ===")
        copy_posters(data_dir)

    # ES
    if not args.skip_es:
        log("=== Step 7: Elasticsearch ===")
        conn2 = psycopg2.connect(PG_DSN)
        index_es(conn2)
        conn2.close()

    # Redis
    if not args.skip_redis:
        log("=== Step 8: Redis ===")
        conn3 = psycopg2.connect(PG_DSN)
        populate_redis(conn3)
        conn3.close()

    # Verify
    conn4 = psycopg2.connect(PG_DSN)
    verify(conn4)
    conn4.close()

    log(f"DONE in {(time.time()-t0)/60:.1f} min")


if __name__ == "__main__":
    main()
