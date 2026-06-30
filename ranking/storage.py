"""CSV persistence for ranking sessions."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from ranking.engine import create_session
from ranking.models import MovieRating, RankingSession

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

CSV_COLUMNS = [
    "rank",
    "movie",
    "rating",
    "rd",
    "volatility",
    "comparisons",
    "wins",
    "losses",
    "last_updated",
]


def sanitize_list_name(name: str) -> str:
    cleaned = re.sub(r"[^\w\s]", "", name.lower())
    cleaned = re.sub(r"\s+", "_", cleaned.strip())
    return cleaned.strip("_")


def csv_filename(list_name: str) -> str:
    return f"df_ranks_{sanitize_list_name(list_name)}.csv"


def csv_path(list_name: str) -> Path:
    return DATA_DIR / csv_filename(list_name)


def ensure_data_dir() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def csv_exists(list_name: str) -> bool:
    return csv_path(list_name).exists()


def parse_movies_text(text: str) -> tuple[list[str], list[str]]:
    """Return (unique movies in order, duplicate names)."""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    seen: set[str] = set()
    unique: list[str] = []
    duplicates: list[str] = []
    for line in lines:
        if line in seen:
            duplicates.append(line)
        else:
            seen.add(line)
            unique.append(line)
    return unique, duplicates


def save_session(session: RankingSession) -> Path:
    ensure_data_dir()
    path = csv_path(session.list_name)

    rows = []
    for rank, movie in enumerate(session.ordered_movies(), start=1):
        rows.append(
            {
                "rank": rank,
                "movie": movie.movie,
                "rating": round(movie.rating, 2),
                "rd": round(movie.rd, 2),
                "volatility": round(movie.volatility, 6),
                "comparisons": movie.comparisons,
                "wins": movie.wins,
                "losses": movie.losses,
                "last_updated": movie.last_updated.isoformat(),
            }
        )

    pd.DataFrame(rows, columns=CSV_COLUMNS).to_csv(path, index=False)
    return path


def load_session(list_name: str) -> RankingSession | None:
    path = csv_path(list_name)
    if not path.exists():
        return None

    df = pd.read_csv(path)
    session = RankingSession(list_name=list_name)

    for _, row in df.iterrows():
        last_updated = datetime.now(timezone.utc)
        if pd.notna(row.get("last_updated")):
            last_updated = datetime.fromisoformat(str(row["last_updated"]))

        movie = MovieRating(
            movie=str(row["movie"]),
            rating=float(row["rating"]),
            rd=float(row["rd"]),
            volatility=float(row["volatility"]),
            comparisons=int(row["comparisons"]),
            wins=int(row["wins"]),
            losses=int(row["losses"]),
            last_updated=last_updated,
        )
        session.movies[movie.movie] = movie

    session.total_comparisons = sum(m.comparisons for m in session.movies.values()) // 2
    return session


def delete_session(list_name: str) -> None:
    path = csv_path(list_name)
    if path.exists():
        path.unlink()


def init_or_resume_session(
    list_name: str, movie_names: list[str], force_new: bool = False
) -> tuple[RankingSession, bool]:
    """Return (session, resumed). Creates new session if no CSV or force_new."""
    if not force_new and csv_exists(list_name):
        loaded = load_session(list_name)
        if loaded is not None:
            return loaded, True

    return create_session(list_name, movie_names), False
