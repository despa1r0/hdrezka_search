CREATE TABLE IF NOT EXISTS users (
    id BIGSERIAL PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS movies (
    id BIGSERIAL PRIMARY KEY,
    rezka_url TEXT NOT NULL UNIQUE,
    title_ru TEXT NOT NULL,
    title_original TEXT,
    year INTEGER,
    content_type TEXT NOT NULL DEFAULT 'film',
    imdb_id TEXT,
    imdb_rating NUMERIC(3, 1),
    imdb_match_confidence NUMERIC(4, 3),
    poster_url TEXT,
    description TEXT,
    source_catalog TEXT,
    parsed_at TIMESTAMPTZ,
    imdb_checked_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS movie_genres (
    movie_id BIGINT NOT NULL REFERENCES movies(id) ON DELETE CASCADE,
    genre TEXT NOT NULL,
    PRIMARY KEY (movie_id, genre)
);

CREATE TABLE IF NOT EXISTS movie_countries (
    movie_id BIGINT NOT NULL REFERENCES movies(id) ON DELETE CASCADE,
    country TEXT NOT NULL,
    PRIMARY KEY (movie_id, country)
);

CREATE TABLE IF NOT EXISTS shown_items (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    movie_id BIGINT NOT NULL REFERENCES movies(id) ON DELETE CASCADE,
    query_hash TEXT NOT NULL,
    shown_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (user_id, movie_id, query_hash)
);

CREATE TABLE IF NOT EXISTS user_movie_state (
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    movie_id BIGINT NOT NULL REFERENCES movies(id) ON DELETE CASCADE,
    state TEXT NOT NULL CHECK (state IN ('seen', 'hidden', 'favorite', 'watchlist')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, movie_id, state)
);

CREATE TABLE IF NOT EXISTS catalog_crawl_state (
    id BIGSERIAL PRIMARY KEY,
    catalog_key TEXT NOT NULL UNIQUE,
    last_page INTEGER NOT NULL DEFAULT 0,
    last_movie_url TEXT,
    status TEXT NOT NULL DEFAULT 'idle',
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS crawl_log (
    id BIGSERIAL PRIMARY KEY,
    catalog_key TEXT,
    movie_id BIGINT REFERENCES movies(id) ON DELETE SET NULL,
    level TEXT NOT NULL DEFAULT 'info',
    message TEXT NOT NULL,
    context JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_movies_imdb_rating ON movies (imdb_rating);
CREATE INDEX IF NOT EXISTS idx_movies_content_type ON movies (content_type);
CREATE INDEX IF NOT EXISTS idx_movies_title_ru_lower ON movies (lower(title_ru));
CREATE INDEX IF NOT EXISTS idx_movie_genres_lower ON movie_genres (lower(genre));
CREATE INDEX IF NOT EXISTS idx_movie_countries_lower ON movie_countries (lower(country));
CREATE INDEX IF NOT EXISTS idx_shown_items_user_query ON shown_items (user_id, query_hash, shown_at);
CREATE INDEX IF NOT EXISTS idx_user_movie_state_user_state ON user_movie_state (user_id, state);

INSERT INTO users (username, display_name)
VALUES ('test1', 'test1'), ('test2', 'test2')
ON CONFLICT (username) DO NOTHING;
