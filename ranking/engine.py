"""Pair selection, stopping logic, and session management."""

from __future__ import annotations

import math
from itertools import combinations

from ranking.glicko import create_movie_rating, record_comparison
from ranking.models import RankingSession

RD_STOP_THRESHOLD = 75.0


def min_comparisons_per_movie(movie_count: int) -> int:
    if movie_count < 2:
        return 0
    return max(3, math.ceil(math.log2(movie_count)))


def create_session(list_name: str, movie_names: list[str]) -> RankingSession:
    session = RankingSession(list_name=list_name)
    for name in movie_names:
        session.movies[name] = create_movie_rating(name)
    return session


def session_from_loaded(list_name: str, session: RankingSession) -> RankingSession:
    session.list_name = list_name
    return session


def select_next_pair(session: RankingSession) -> tuple[str, str] | None:
    """Pick the pair with highest combined uncertainty and similar ratings."""
    names = list(session.movies.keys())
    if len(names) < 2:
        return None

    best_pair: tuple[str, str] | None = None
    best_score = float("-inf")

    for a, b in combinations(names, 2):
        movie_a = session.get(a)
        movie_b = session.get(b)
        combined_rd = movie_a.rd + movie_b.rd
        rating_gap = abs(movie_a.rating - movie_b.rating)
        # Higher RD and closer ratings = more informative comparison
        score = combined_rd - (rating_gap * 0.05)
        if score > best_score:
            best_score = score
            best_pair = (a, b)

    return best_pair


def is_ranking_complete(session: RankingSession) -> bool:
    if session.movie_count < 2:
        return True

    min_per_movie = min_comparisons_per_movie(session.movie_count)
    avg_comparisons = session.total_comparisons / session.movie_count
    all_rd_low = all(m.rd <= RD_STOP_THRESHOLD for m in session.movies.values())

    return all_rd_low and avg_comparisons >= min_per_movie


def apply_comparison(
    session: RankingSession, winner_name: str, loser_name: str
) -> None:
    record_comparison(session.get(winner_name), session.get(loser_name))
    session.total_comparisons += 1


def add_movie(session: RankingSession, movie_name: str) -> str | None:
    """Add a movie mid-ranking. Returns an error message, or None on success."""
    name = movie_name.strip()
    if not name:
        return "Enter a movie name."
    if name in session.movies:
        return f'"{name}" is already in your list.'
    session.movies[name] = create_movie_rating(name)
    return None


def progress_label(session: RankingSession) -> str:
    avg_rd = session.average_rd
    return (
        f"Comparisons: {session.total_comparisons} · "
        f"Avg uncertainty (RD): {avg_rd:.0f}"
    )
