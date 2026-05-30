"""Import MovieLens 1M into PostgreSQL + Elasticsearch + Redis"""
import psycopg2, redis, os
from collections import Counter, defaultdict
from psycopg2.extras import execute_values
from elasticsearch import Elasticsearch, helpers

PG_DSN = "dbname=rec_db user=rec password=rec123 host=localhost port=5432"
ES_URL = "http://localhost:9200"
REDIS_HOST = "localhost"
DATA_DIR = os.path.join(os.path.dirname(__file__), "data", "ml-1m")

MOVIE_GENRES = [
    "Action","Adventure","Animation","Children's","Comedy","Crime","Documentary",
    "Drama","Fantasy","Film-Noir","Horror","Musical","Mystery","Romance","Sci-Fi",
    "Thriller","War","Western"
]

def parse_users(path):
    users = []
    with open(path, encoding="latin-1") as f:
        for line in f:
            uid, gender, age, occ, zipc = line.strip().split("::")
            users.append((int(uid), gender, int(age), int(occ), zipc))
    return users

def parse_movies(path):
    movies, genres_by_mid = [], {}
    with open(path, encoding="latin-1") as f:
        for line in f:
            mid, title, genres_str = line.strip().split("::")
            genres = [g.strip() for g in genres_str.split("|") if g.strip()]
            year = None
            if "(" in title and title.rstrip().endswith(")"):
                try: year = int(title[-5:-1]); title = title[:-7].strip()
                except: pass
            movies.append((int(mid), title, year, genres))
            genres_by_mid[int(mid)] = genres
    return movies, genres_by_mid

def parse_ratings(path):
    ratings = []
    with open(path, encoding="latin-1") as f:
        for line in f:
            uid, mid, rating, ts = line.strip().split("::")
            ratings.append((int(uid), int(mid), int(rating), int(ts)))
    return ratings

def import_pg(users, movies, ratings):
    conn = psycopg2.connect(PG_DSN)
    cur = conn.cursor()

    # Genres
    for g in MOVIE_GENRES:
        cur.execute("INSERT INTO genres (name) VALUES (%s) ON CONFLICT (name) DO NOTHING", (g,))

    # Users
    print(f"Inserting {len(users)} users...")
    user_data = [(u[0], f"u{u[0]}@rec.dev", f"user{u[0]}", "pw", u[1], str(u[2]), str(u[3]), u[4]) for u in users]
    execute_values(cur,
        "INSERT INTO users (user_id, email, username, hashed_password, is_active, gender, age, occupation, zip_code) VALUES %s ON CONFLICT (user_id) DO NOTHING",
        user_data, template="(%s,%s,%s,%s,1,%s,%s,%s,%s)")

    # Movies
    print(f"Inserting {len(movies)} movies...")
    movie_data = [(m[0], m[1], m[2], "{" + ",".join(g.replace("'","''") for g in m[3]) + "}") for m in movies]
    execute_values(cur,
        "INSERT INTO movies (movie_id, title, year, genres, avg_rating, rating_count) VALUES %s ON CONFLICT (movie_id) DO NOTHING",
        movie_data, template="(%s,%s,%s,%s::text[],0,0)")

    # Ratings in batch
    print(f"Inserting {len(ratings)} ratings...")
    for i in range(0, len(ratings), 5000):
        chunk = ratings[i:i+5000]
        execute_values(cur,
            "INSERT INTO ratings (user_id, movie_id, rating, timestamp) VALUES %s ON CONFLICT (user_id, movie_id) DO NOTHING",
            chunk, template="(%s,%s,%s,%s)")
        conn.commit()

    # Update avg_rating
    print("Updating avg_rating...")
    cur.execute("UPDATE movies m SET avg_rating = (SELECT COALESCE(AVG(r.rating)::float, 0) FROM ratings r WHERE r.movie_id = m.movie_id), rating_count = (SELECT COUNT(*) FROM ratings r WHERE r.movie_id = m.movie_id)")
    conn.commit(); cur.close(); conn.close()
    print("PG done.")

def import_es():
    es = Elasticsearch(ES_URL)
    es.indices.delete(index="movies", ignore=[404])
    es.indices.create(index="movies", body={
        "mappings": {"properties": {
            "movie_id": {"type": "long"}, "title": {"type": "text"},
            "year": {"type": "integer"}, "genres": {"type": "keyword"},
            "avg_rating": {"type": "float"}, "rating_count": {"type": "integer"},
            "description": {"type": "text"},
        }}
    })

    pg = psycopg2.connect(PG_DSN)
    cur = pg.cursor()
    cur.execute("SELECT movie_id, title, year, genres, avg_rating, rating_count FROM movies")
    actions = []
    for row in cur.fetchall():
        actions.append({"_index": "movies", "_id": row[0], "_source": {
            "movie_id": row[0], "title": row[1], "year": row[2],
            "genres": (row[3].split(",") if isinstance(row[3], str) else row[3]) if row[3] else [],
            "avg_rating": row[4] or 0, "rating_count": row[5] or 0,
        }})
    helpers.bulk(es, actions)
    cur.close(); pg.close()
    print(f"ES done: {len(actions)} movies indexed.")

def import_redis(ratings, users, genres_by_mid):
    r = redis.Redis(host=REDIS_HOST, port=6379, decode_responses=True)
    r.flushall()

    user_info = {u[0]: u for u in users}
    user_ratings = defaultdict(list)
    for uid, mid, rating, ts in ratings:
        user_ratings[uid].append((mid, rating, ts))

    for uid, rated in user_ratings.items():
        rated.sort(key=lambda x: x[2], reverse=True)
        # History
        for mid, _, _ in rated[:100]:
            r.lpush(f"user:{uid}:history", mid)
        # Profile
        info = user_info.get(uid)
        profile = {"frequent_genres": ""}
        if info:
            profile = {"gender": info[1], "age": str(info[2]), "occupation": str(info[3]), "zip_code": info[4], "frequent_genres": ""}
        # Top-3 frequent genres
        genre_counter = Counter()
        genre_rewards = defaultdict(lambda: [0, 0])  # {genre: [n, total_reward]}
        for mid, rating_val, _ in rated:
            for g in genres_by_mid.get(mid, []):
                genre_counter[g] += 1
                genre_rewards[g][0] += 1
                genre_rewards[g][1] += rating_val
        top_genres = [g for g, _ in genre_counter.most_common(3)]
        profile["frequent_genres"] = ",".join(top_genres)
        r.hset(f"user:{uid}:profile", mapping=profile)
        # UCB stats
        for g, (n, reward) in genre_rewards.items():
            r.hset(f"user:{uid}:genre_ucb", g, f"{n}:{reward}")

    print(f"Redis done: {len(user_ratings)} users.")

if __name__ == "__main__":
    print("Parsing ML-1M...")
    users = parse_users(os.path.join(DATA_DIR, "users.dat"))
    movies, genres_by_mid = parse_movies(os.path.join(DATA_DIR, "movies.dat"))
    ratings = parse_ratings(os.path.join(DATA_DIR, "ratings.dat"))
    print(f"{len(users)} users, {len(movies)} movies, {len(ratings)} ratings")

    print("\n=== PostgreSQL ===")
    import_pg(users, movies, ratings)
    print("\n=== Elasticsearch ===")
    import_es()
    print("\n=== Redis ===")
    import_redis(ratings, users, genres_by_mid)
    print("\nALL DONE.")
