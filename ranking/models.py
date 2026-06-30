from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


DEFAULT_RATING = 1500.0
DEFAULT_RD = 350.0
DEFAULT_VOLATILITY = 0.06


@dataclass
class MovieRating:
    movie: str
    rating: float = DEFAULT_RATING
    rd: float = DEFAULT_RD
    volatility: float = DEFAULT_VOLATILITY
    comparisons: int = 0
    wins: int = 0
    losses: int = 0
    last_updated: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    def snapshot(self) -> tuple[float, float, float]:
        return self.rating, self.rd, self.volatility


@dataclass
class RankingSession:
    list_name: str
    movies: dict[str, MovieRating] = field(default_factory=dict)
    total_comparisons: int = 0

    @property
    def movie_count(self) -> int:
        return len(self.movies)

    @property
    def average_rd(self) -> float:
        if not self.movies:
            return DEFAULT_RD
        return sum(m.rd for m in self.movies.values()) / len(self.movies)

    def get(self, movie: str) -> MovieRating:
        return self.movies[movie]

    def ordered_movies(self) -> list[MovieRating]:
        return sorted(
            self.movies.values(),
            key=lambda m: (-m.rating, m.movie.lower()),
        )
