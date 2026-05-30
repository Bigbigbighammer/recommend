CREATE TABLE IF NOT EXISTS users (
    user_id       IDENTITY PRIMARY KEY,
    email         VARCHAR(255),
    username      VARCHAR(100),
    hashed_password VARCHAR(255),
    is_active     SMALLINT DEFAULT 1,
    is_superuser  SMALLINT DEFAULT 0,
    gender        VARCHAR(1),
    age           VARCHAR(20),
    occupation    VARCHAR(100),
    zip_code      VARCHAR(10),
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    preferred_genres VARCHAR(500)
);
ALTER TABLE users ADD CONSTRAINT IF NOT EXISTS uq_users_email UNIQUE (email);
ALTER TABLE users ADD CONSTRAINT IF NOT EXISTS uq_users_username UNIQUE (username);

CREATE TABLE IF NOT EXISTS movies (
    movie_id        IDENTITY PRIMARY KEY,
    imdb_id         VARCHAR(20),
    title           VARCHAR(255),
    year            INTEGER,
    genres          VARCHAR(500),
    description     VARCHAR(4000),
    avg_rating      FLOAT,
    rating_count    INTEGER DEFAULT 0,
    imdb_rating     FLOAT,
    imdb_votes      INTEGER,
    title_type      VARCHAR(50),
    runtime_minutes INTEGER,
    is_adult        SMALLINT DEFAULT 0,
    created_by      INTEGER
);
ALTER TABLE movies ADD CONSTRAINT IF NOT EXISTS uq_movies_imdb_id UNIQUE (imdb_id);

CREATE TABLE IF NOT EXISTS ratings (
    user_id   INTEGER,
    movie_id  INTEGER,
    rating    INTEGER CHECK (rating >= 1 AND rating <= 10),
    timestamp BIGINT,
    PRIMARY KEY (user_id, movie_id)
);

CREATE TABLE IF NOT EXISTS genres (
    id   IDENTITY PRIMARY KEY,
    name VARCHAR(50)
);
ALTER TABLE genres ADD CONSTRAINT IF NOT EXISTS uq_genres_name UNIQUE (name);

CREATE TABLE IF NOT EXISTS title_ratings (
    tconst         VARCHAR(20) PRIMARY KEY,
    average_rating FLOAT,
    num_votes      INTEGER
);

CREATE TABLE IF NOT EXISTS name_basics (
    nconst             VARCHAR(20) PRIMARY KEY,
    primary_name       VARCHAR(255),
    birth_year         INTEGER,
    death_year         INTEGER,
    primary_profession VARCHAR(500),
    known_for_titles   VARCHAR(500)
);

CREATE TABLE IF NOT EXISTS title_crew (
    tconst    VARCHAR(20) PRIMARY KEY,
    directors VARCHAR(1000),
    writers   VARCHAR(1000)
);

CREATE TABLE IF NOT EXISTS title_principals (
    tconst     VARCHAR(20),
    ordering   INTEGER,
    nconst     VARCHAR(20),
    category   VARCHAR(50),
    job        VARCHAR(255),
    characters VARCHAR(2000),
    PRIMARY KEY (tconst, ordering)
);

CREATE TABLE IF NOT EXISTS title_akas (
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

-- Seed data
INSERT INTO genres (name) VALUES ('Action'), ('Comedy'), ('Drama'), ('Horror'), ('Sci-Fi'), ('Romance');

INSERT INTO users (user_id, email, username, hashed_password, is_active, gender, age, occupation, preferred_genres)
VALUES (1, 'test@rec.dev', 'testuser', 'test123', 1, 'M', '25', 'engineer', 'Action,Sci-Fi,Drama');

INSERT INTO movies (movie_id, imdb_id, title, year, genres, description, avg_rating, rating_count, imdb_rating, imdb_votes, runtime_minutes)
VALUES
(1, 'tt0111161', 'The Shawshank Redemption', 1994, 'Drama', 'Two imprisoned men bond over a number of years.', 9.3, 100, 9.3, 2900000, 142),
(2, 'tt0068646', 'The Godfather', 1972, 'Crime,Drama', 'The aging patriarch of an organized crime dynasty transfers control to his son.', 9.2, 90, 9.2, 2000000, 175),
(3, 'tt0468569', 'The Dark Knight', 2008, 'Action,Crime,Drama', 'When the menace known as the Joker wreaks havoc on Gotham, Batman must accept one of the greatest tests.', 9.0, 85, 9.0, 2800000, 152),
(4, 'tt0110912', 'Pulp Fiction', 1994, 'Crime,Drama', 'The lives of two mob hitmen, a boxer, a gangster and his wife intertwine.', 8.9, 80, 8.9, 2200000, 154),
(5, 'tt0108052', 'Schindlers List', 1993, 'Drama,History,War', 'In German-occupied Poland, Oskar Schindler becomes concerned for his Jewish workforce.', 9.0, 75, 9.0, 1400000, 195),
(6, 'tt0167260', 'The Lord of the Rings: The Return of the King', 2003, 'Action,Adventure,Drama', 'Gandalf and Aragorn lead the World of Men against Sauron.', 8.9, 70, 8.9, 1900000, 201),
(7, 'tt0137523', 'Fight Club', 1999, 'Drama', 'An insomniac office worker and a devil-may-care soap maker form an underground fight club.', 8.8, 65, 8.8, 2200000, 139),
(8, 'tt0120737', 'The Matrix', 1999, 'Action,Sci-Fi', 'A computer hacker learns about the true nature of reality.', 8.7, 60, 8.7, 2000000, 136),
(9, 'tt0816692', 'Interstellar', 2014, 'Adventure,Drama,Sci-Fi', 'A team of explorers travel through a wormhole in space.', 8.6, 55, 8.6, 1900000, 169),
(10, 'tt1375666', 'Inception', 2010, 'Action,Adventure,Sci-Fi', 'A thief who steals corporate secrets uses dream-sharing technology.', 8.8, 50, 8.8, 2500000, 148);

INSERT INTO ratings (user_id, movie_id, rating, timestamp)
VALUES
(1, 1, 9, 1700000000000),
(1, 2, 8, 1700000001000),
(1, 3, 10, 1700000002000);
