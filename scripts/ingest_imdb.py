"""Download and import IMDb datasets into PostgreSQL.

Downloads 6 TSV.gz files from https://datasets.imdbws.com/, imports them
into PG with batch INSERT (via execute_values), then links the movies
table to IMDb IDs by title+year matching and fills in IMDb metadata.
"""

import csv
import gzip
import os
import re
import sys
import time
import urllib.request
from pathlib import Path

import psycopg2
from psycopg2.extras import execute_values

IMDB_BASE = "https://datasets.imdbws.com/"
DATASETS = [
    "title.basics.tsv.gz",
    "title.ratings.tsv.gz",
    "name.basics.tsv.gz",
    "title.principals.tsv.gz",
    "title.crew.tsv.gz",
    "title.akas.tsv.gz",
]

PG_DSN = os.environ.get("PG_DSN", "dbname=rec_db user=rec password=rec123 host=localhost port=5432")
DATA_DIR = Path(os.environ.get("DATA_DIR", Path(__file__).resolve().parent / "data" / "imdb"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

BATCH = 5000


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


# ── download ────────────────────────────────────────────────────────

def download():
    for name in DATASETS:
        path = DATA_DIR / name
        if path.exists():
            log(f"SKIP {name} ({path.stat().st_size / 1024**2:.0f} MB)")
            continue
        url = IMDB_BASE + name
        log(f"GET  {url}")
        urllib.request.urlretrieve(url, path)
        log(f"     {name}  {path.stat().st_size / 1024**2:.0f} MB")


# ── schema ──────────────────────────────────────────────────────────

SCHEMA = """
CREATE TABLE IF NOT EXISTS title_basics (
    tconst         VARCHAR(20) PRIMARY KEY,
    title_type     VARCHAR(50),
    primary_title  VARCHAR(500),
    original_title VARCHAR(500),
    is_adult       SMALLINT,
    start_year     INTEGER,
    end_year       INTEGER,
    runtime_minutes INTEGER,
    genres         TEXT[]
);
CREATE INDEX IF NOT EXISTS idx_tb_title ON title_basics(primary_title);
CREATE INDEX IF NOT EXISTS idx_tb_year  ON title_basics(start_year);
"""


def init_schema(conn):
    cur = conn.cursor()
    cur.execute(SCHEMA)
    conn.commit()
    cur.close()
    log("Schema ready")


# ── import helpers ──────────────────────────────────────────────────

def read_tsv(path):
    """Read a .gz TSV file, yielding lists of fields.  Handles \\N -> None."""
    with gzip.open(path, "rt", encoding="utf-8") as f:
        reader = csv.reader(f, delimiter="\t", quoting=csv.QUOTE_NONE)
        header = next(reader)
        for fields in reader:
            out = []
            for v in fields:
                if v == "\\N":
                    out.append(None)
                else:
                    out.append(v.replace("\n", " ").replace("\r", " "))
            yield header, out


def bulk_insert(conn, table, columns, rows, template, on_conflict=""):
    cur = conn.cursor()
    sql = f"INSERT INTO {table} ({columns}) VALUES %s"
    if on_conflict:
        sql += f" ON CONFLICT {on_conflict} DO NOTHING"
    execute_values(cur, sql, rows, template=template)
    conn.commit()
    cur.close()


# ── per-dataset importers ───────────────────────────────────────────

def import_title_basics(conn):
    path = DATA_DIR / "title.basics.tsv.gz"
    log(f"Importing {path.name} ...")
    batch, count = [], 0
    for _, f in read_tsv(path):
        genres = None
        if f[8] is not None:
            genres = "{" + f[8] + "}"
        batch.append((f[0], f[1], f[2], f[3],
                      int(f[4]) if f[4] else 0,
                      int(f[5]) if f[5] else None,
                      int(f[6]) if f[6] else None,
                      int(f[7]) if f[7] else None,
                      genres))
        count += 1
        if len(batch) >= BATCH:
            bulk_insert(conn, "title_basics",
                "tconst,title_type,primary_title,original_title,is_adult,start_year,end_year,runtime_minutes,genres",
                batch,
                "(%s,%s,%s,%s,%s,%s,%s,%s,%s::text[])",
                "(tconst) DO UPDATE SET title_type=EXCLUDED.title_type,primary_title=EXCLUDED.primary_title,original_title=EXCLUDED.original_title,is_adult=EXCLUDED.is_adult,start_year=EXCLUDED.start_year,end_year=EXCLUDED.end_year,runtime_minutes=EXCLUDED.runtime_minutes,genres=EXCLUDED.genres")
            batch.clear()
            log(f"  {count:,} rows ...")
    if batch:
        bulk_insert(conn, "title_basics",
            "tconst,title_type,primary_title,original_title,is_adult,start_year,end_year,runtime_minutes,genres",
            batch,
            "(%s,%s,%s,%s,%s,%s,%s,%s,%s::text[])",
            "(tconst) DO UPDATE SET title_type=EXCLUDED.title_type,primary_title=EXCLUDED.primary_title,original_title=EXCLUDED.original_title,is_adult=EXCLUDED.is_adult,start_year=EXCLUDED.start_year,end_year=EXCLUDED.end_year,runtime_minutes=EXCLUDED.runtime_minutes,genres=EXCLUDED.genres")
    log(f"title_basics: {count:,} rows imported")


def import_title_ratings(conn):
    path = DATA_DIR / "title.ratings.tsv.gz"
    log(f"Importing {path.name} ...")
    batch, count = [], 0
    for _, f in read_tsv(path):
        batch.append((f[0], float(f[1]), int(f[2])))
        count += 1
        if len(batch) >= BATCH:
            bulk_insert(conn, "title_ratings",
                "tconst,average_rating,num_votes",
                batch, "(%s,%s,%s)",
                "(tconst) DO UPDATE SET average_rating=EXCLUDED.average_rating,num_votes=EXCLUDED.num_votes")
            batch.clear()
            log(f"  {count:,} rows ...")
    if batch:
        bulk_insert(conn, "title_ratings",
            "tconst,average_rating,num_votes",
            batch, "(%s,%s,%s)",
            "(tconst) DO UPDATE SET average_rating=EXCLUDED.average_rating,num_votes=EXCLUDED.num_votes")
    log(f"title_ratings: {count:,} rows imported")


def import_name_basics(conn):
    path = DATA_DIR / "name.basics.tsv.gz"
    log(f"Importing {path.name} ...")
    batch, count = [], 0
    for _, f in read_tsv(path):
        prof = f[4]
        known = f[5]
        batch.append((
            f[0], f[1],
            int(f[2]) if f[2] else None,
            int(f[3]) if f[3] else None,
            "{" + prof + "}" if prof else None,
            "{" + known + "}" if known else None,
        ))
        count += 1
        if len(batch) >= BATCH:
            bulk_insert(conn, "name_basics",
                "nconst,primary_name,birth_year,death_year,primary_profession,known_for_titles",
                batch, "(%s,%s,%s,%s,%s::text[],%s::text[])",
                "(nconst) DO UPDATE SET primary_name=EXCLUDED.primary_name,birth_year=EXCLUDED.birth_year,death_year=EXCLUDED.death_year,primary_profession=EXCLUDED.primary_profession,known_for_titles=EXCLUDED.known_for_titles")
            batch.clear()
            log(f"  {count:,} rows ...")
    if batch:
        bulk_insert(conn, "name_basics",
            "nconst,primary_name,birth_year,death_year,primary_profession,known_for_titles",
            batch, "(%s,%s,%s,%s,%s::text[],%s::text[])",
            "(nconst) DO UPDATE SET primary_name=EXCLUDED.primary_name,birth_year=EXCLUDED.birth_year,death_year=EXCLUDED.death_year,primary_profession=EXCLUDED.primary_profession,known_for_titles=EXCLUDED.known_for_titles")
    log(f"name_basics: {count:,} rows imported")


def import_title_principals(conn):
    path = DATA_DIR / "title.principals.tsv.gz"
    log(f"Importing {path.name} ...")
    batch, count = [], 0
    for _, f in read_tsv(path):
        batch.append((f[0], int(f[1]), f[2], f[3], f[4], f[5]))
        count += 1
        if len(batch) >= BATCH:
            bulk_insert(conn, "title_principals",
                "tconst,ordering,nconst,category,job,characters",
                batch, "(%s,%s,%s,%s,%s,%s)",
                "(tconst,ordering) DO UPDATE SET nconst=EXCLUDED.nconst,category=EXCLUDED.category,job=EXCLUDED.job,characters=EXCLUDED.characters")
            batch.clear()
            log(f"  {count:,} rows ...")
    if batch:
        bulk_insert(conn, "title_principals",
            "tconst,ordering,nconst,category,job,characters",
            batch, "(%s,%s,%s,%s,%s,%s)",
            "(tconst,ordering) DO UPDATE SET nconst=EXCLUDED.nconst,category=EXCLUDED.category,job=EXCLUDED.job,characters=EXCLUDED.characters")
    log(f"title_principals: {count:,} rows imported")


def import_title_crew(conn):
    path = DATA_DIR / "title.crew.tsv.gz"
    log(f"Importing {path.name} ...")
    batch, count = [], 0
    for _, f in read_tsv(path):
        dirs = f[1]
        wrs = f[2]
        batch.append((
            f[0],
            "{" + dirs + "}" if dirs else None,
            "{" + wrs + "}" if wrs else None,
        ))
        count += 1
        if len(batch) >= BATCH:
            bulk_insert(conn, "title_crew",
                "tconst,directors,writers",
                batch, "(%s,%s::text[],%s::text[])",
                "(tconst) DO UPDATE SET directors=EXCLUDED.directors,writers=EXCLUDED.writers")
            batch.clear()
            log(f"  {count:,} rows ...")
    if batch:
        bulk_insert(conn, "title_crew",
            "tconst,directors,writers",
            batch, "(%s,%s::text[],%s::text[])",
            "(tconst) DO UPDATE SET directors=EXCLUDED.directors,writers=EXCLUDED.writers")
    log(f"title_crew: {count:,} rows imported")


def import_title_akas(conn):
    path = DATA_DIR / "title.akas.tsv.gz"
    log(f"Importing {path.name} ...")
    batch, count = [], 0
    for _, f in read_tsv(path):
        batch.append((
            f[0], int(f[1]), f[2], f[3], f[4], f[5], f[6],
            int(f[7]) if f[7] else 0,
        ))
        count += 1
        if len(batch) >= BATCH:
            bulk_insert(conn, "title_akas",
                "tconst,ordering,title,region,language,types,attributes,is_original_title",
                batch, "(%s,%s,%s,%s,%s,%s,%s,%s)",
                "(tconst,ordering) DO UPDATE SET title=EXCLUDED.title,region=EXCLUDED.region,language=EXCLUDED.language,types=EXCLUDED.types,attributes=EXCLUDED.attributes,is_original_title=EXCLUDED.is_original_title")
            batch.clear()
            log(f"  {count:,} rows ...")
    if batch:
        bulk_insert(conn, "title_akas",
            "tconst,ordering,title,region,language,types,attributes,is_original_title",
            batch, "(%s,%s,%s,%s,%s,%s,%s,%s)",
            "(tconst,ordering) DO UPDATE SET title=EXCLUDED.title,region=EXCLUDED.region,language=EXCLUDED.language,types=EXCLUDED.types,attributes=EXCLUDED.attributes,is_original_title=EXCLUDED.is_original_title")
    log(f"title_akas: {count:,} rows imported")


# ── movie ↔ IMDb linking ───────────────────────────────────────────

def normalize_title(t):
    t = t.lower().strip()
    t = re.sub(r'[^a-z0-9\s]', '', t)
    t = re.sub(r'\s+', ' ', t)
    return t.strip()


def link_and_update_movies(conn):
    """Match movies to IMDb IDs by title+year, then update metadata."""
    log("Linking movies to IMDb ...")
    cur = conn.cursor()

    # Build IMDb lookup: (normalized_title, year) → tconst
    cur.execute("""
        SELECT tconst, primary_title, start_year
        FROM title_basics
        WHERE title_type IN ('movie','tvMovie','short','video')
    """)
    imdb_lookup = {}
    for tconst, title, year in cur.fetchall():
        if title:
            key = (normalize_title(title), year)
            if key not in imdb_lookup:
                imdb_lookup[key] = tconst
    log(f"  IMDb lookup: {len(imdb_lookup):,} unique (title, year) pairs")

    # Get unmatched movies
    cur.execute("SELECT movie_id, title, year FROM movies WHERE imdb_id IS NULL")
    unmatched = cur.fetchall()
    log(f"  Movies to match: {len(unmatched)}")

    matches, skipped = [], 0
    for movie_id, title, year in unmatched:
        key = (normalize_title(title), year)
        tconst = imdb_lookup.get(key)
        if tconst:
            matches.append((tconst, movie_id))
        else:
            skipped += 1
    log(f"  Matched: {len(matches)}, no match: {skipped}")

    # Batch update imdb_id
    for i in range(0, len(matches), 5000):
        chunk = matches[i:i + 5000]
        execute_values(cur, """UPDATE movies SET imdb_id = data.imdb_id
            FROM (VALUES %s) AS data(imdb_id, movie_id)
            WHERE movies.movie_id = data.movie_id""",
            chunk, template="(%s,%s)")
        conn.commit()
    log("  imdb_id linkage complete")

    # Update IMDb metadata columns from title_basics + title_ratings
    log("Updating movies with IMDb metadata ...")
    cur.execute("""
        UPDATE movies m SET
            title_type      = tb.title_type,
            runtime_minutes = tb.runtime_minutes,
            is_adult        = tb.is_adult,
            imdb_rating     = tr.average_rating,
            imdb_votes      = tr.num_votes
        FROM title_basics tb
        LEFT JOIN title_ratings tr ON tb.tconst = tr.tconst
        WHERE m.imdb_id = tb.tconst
          AND m.imdb_id IS NOT NULL
    """)
    updated = cur.rowcount
    conn.commit()
    log(f"  Updated {updated} movies with IMDb metadata")
    cur.close()


# ── verify ──────────────────────────────────────────────────────────

def verify(conn):
    cur = conn.cursor()
    tables = ["title_basics", "title_ratings", "name_basics",
              "title_principals", "title_crew", "title_akas"]
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
    t0 = time.time()

    log("=== Step 1: Download ===")
    download()

    conn = psycopg2.connect(PG_DSN)

    log("=== Step 2: Schema ===")
    init_schema(conn)

    log("=== Step 3: Import ===")
    import_title_basics(conn)
    import_title_ratings(conn)
    import_name_basics(conn)
    import_title_principals(conn)
    import_title_crew(conn)
    import_title_akas(conn)

    log("=== Step 4: Link & update ===")
    link_and_update_movies(conn)

    conn.close()

    conn2 = psycopg2.connect(PG_DSN)
    verify(conn2)
    conn2.close()

    log(f"DONE in {(time.time()-t0)/60:.1f} min")


if __name__ == "__main__":
    main()
