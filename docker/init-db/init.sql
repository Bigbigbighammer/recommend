-- 1. Users
CREATE TABLE users (
    user_id       SERIAL PRIMARY KEY,
    email         VARCHAR(255) UNIQUE,
    username      VARCHAR(100) UNIQUE,
    hashed_password VARCHAR(255),
    is_active     SMALLINT DEFAULT 1,
    is_superuser  SMALLINT DEFAULT 0,
    gender        CHAR(1),
    age           VARCHAR(20),
    occupation    VARCHAR(100),
    zip_code      VARCHAR(10),
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    preferred_genres TEXT[]
);

-- 2. Movies
CREATE TABLE movies (
    movie_id        SERIAL PRIMARY KEY,
    imdb_id         VARCHAR(20) UNIQUE,
    title           VARCHAR(255),
    year            INTEGER,
    genres          TEXT[],
    description     TEXT,
    avg_rating      FLOAT,
    rating_count    INTEGER DEFAULT 0,
    imdb_rating     FLOAT,
    imdb_votes      INTEGER,
    title_type      VARCHAR(50),
    runtime_minutes INTEGER,
    is_adult        SMALLINT DEFAULT 0,
    created_by      INTEGER REFERENCES users(user_id)
);

CREATE INDEX idx_movies_title ON movies(title);
CREATE INDEX idx_movies_year ON movies(year);
CREATE INDEX idx_movies_avg_rating ON movies(avg_rating);
CREATE INDEX idx_movies_imdb_rating ON movies(imdb_rating);

-- 3. Ratings
CREATE TABLE ratings (
    user_id   INTEGER REFERENCES users(user_id),
    movie_id  INTEGER REFERENCES movies(movie_id),
    rating    INTEGER CHECK (rating >= 1 AND rating <= 10),
    timestamp BIGINT,
    PRIMARY KEY (user_id, movie_id)
);

-- 4. Genres
CREATE TABLE genres (
    id   SERIAL PRIMARY KEY,
    name VARCHAR(50) UNIQUE
);

-- 5. IMDb Title Ratings
CREATE TABLE title_ratings (
    tconst         VARCHAR(20) PRIMARY KEY,
    average_rating FLOAT,
    num_votes      INTEGER
);

CREATE INDEX idx_title_ratings_avg ON title_ratings(average_rating);
CREATE INDEX idx_title_ratings_votes ON title_ratings(num_votes);

-- 6. IMDb People
CREATE TABLE name_basics (
    nconst             VARCHAR(20) PRIMARY KEY,
    primary_name       VARCHAR(255),
    birth_year         INTEGER,
    death_year         INTEGER,
    primary_profession TEXT[],
    known_for_titles   TEXT[]
);

CREATE INDEX idx_name_basics_name ON name_basics(primary_name);

-- 7. IMDb Crew
CREATE TABLE title_crew (
    tconst    VARCHAR(20) PRIMARY KEY,
    directors TEXT[],
    writers   TEXT[]
);

-- 8. IMDb Principals
CREATE TABLE title_principals (
    tconst     VARCHAR(20),
    ordering   INTEGER,
    nconst     VARCHAR(20),
    category   VARCHAR(50),
    job        VARCHAR(255),
    characters TEXT,
    PRIMARY KEY (tconst, ordering)
);

CREATE INDEX idx_title_principals_nconst ON title_principals(nconst);

-- 9. IMDb AKA
CREATE TABLE title_akas (
    tconst           VARCHAR(20),
    ordering         INTEGER,
    title            VARCHAR(500),
    region           VARCHAR(10),
    language         VARCHAR(10),
    types            VARCHAR(100),
    attributes       VARCHAR(255),
    is_original_title SMALLINT,
    PRIMARY KEY (tconst, ordering)
);

CREATE INDEX idx_title_akas_title ON title_akas(title);

-- Seed test user
INSERT INTO genres (name) VALUES ('Action'), ('Comedy'), ('Drama'), ('Horror'), ('Sci-Fi'), ('Romance');
