"""Glicko-2 rating updates for pairwise comparisons."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timezone

from ranking.models import MovieRating

_SCALE = 173.7178
_TAU = 0.5
_EPSILON = 0.000001


@dataclass
class _Rating:
    mu: float
    phi: float
    sigma: float


def _scale_down(rating: float, rd: float, sigma: float) -> _Rating:
    return _Rating(
        mu=(rating - 1500.0) / _SCALE,
        phi=rd / _SCALE,
        sigma=sigma,
    )


def _scale_up(rating: _Rating) -> tuple[float, float, float]:
    return (
        rating.mu * _SCALE + 1500.0,
        rating.phi * _SCALE,
        rating.sigma,
    )


def _g(phi: float) -> float:
    return 1.0 / math.sqrt(1.0 + 3.0 * phi * phi / (math.pi**2))


def _expected(mu: float, mu_j: float, phi_j: float) -> float:
    return 1.0 / (1.0 + math.exp(-_g(phi_j) * (mu - mu_j)))


def _determine_sigma(rating: _Rating, difference: float, variance: float) -> float:
    phi = rating.phi
    difference_squared = difference**2
    alpha = math.log(rating.sigma**2)

    def f(x: float) -> float:
        tmp = phi**2 + variance + math.exp(x)
        return (math.exp(x) * (difference_squared - tmp) / (2.0 * tmp**2)) - (
            (x - alpha) / (_TAU**2)
        )

    a = alpha
    if difference_squared > phi**2 + variance:
        b = math.log(difference_squared - phi**2 - variance)
    else:
        k = 1
        while f(alpha - k * math.sqrt(_TAU**2)) < 0:
            k += 1
        b = alpha - k * math.sqrt(_TAU**2)

    f_a, f_b = f(a), f(b)
    while abs(b - a) > _EPSILON:
        c = a + (a - b) * f_a / (f_b - f_a)
        f_c = f(c)
        if f_c * f_b < 0:
            a, f_a = b, f_b
        else:
            f_a /= 2.0
        b, f_b = c, f_c

    return math.exp(a / 2.0)


def _rate_against(
    rating: float,
    rd: float,
    volatility: float,
    opponent_rating: float,
    opponent_rd: float,
    score: float,
) -> tuple[float, float, float]:
    """Update one player from a single comparison."""
    player = _scale_down(rating, rd, volatility)
    opponent = _scale_down(opponent_rating, opponent_rd, volatility)

    impact = _g(opponent.phi)
    expected = _expected(player.mu, opponent.mu, opponent.phi)

    variance_inv = impact**2 * expected * (1.0 - expected)
    variance = 1.0 / variance_inv
    difference = (impact * (score - expected)) / variance_inv

    sigma = _determine_sigma(player, difference, variance)
    phi_star = math.sqrt(player.phi**2 + sigma**2)
    phi = 1.0 / math.sqrt(1.0 / phi_star**2 + 1.0 / variance)
    mu = player.mu + phi**2 * (difference / variance)

    return _scale_up(_Rating(mu=mu, phi=phi, sigma=sigma))


def create_movie_rating(movie: str) -> MovieRating:
    return MovieRating(movie=movie)


def record_comparison(winner: MovieRating, loser: MovieRating) -> None:
    """Update both players after winner is chosen over loser."""
    now = datetime.now(timezone.utc)

    w_rating, w_rd, w_vol = winner.snapshot()
    l_rating, l_rd, l_vol = loser.snapshot()

    new_w = _rate_against(w_rating, w_rd, w_vol, l_rating, l_rd, 1.0)
    new_l = _rate_against(l_rating, l_rd, l_vol, w_rating, w_rd, 0.0)

    winner.rating, winner.rd, winner.volatility = new_w
    loser.rating, loser.rd, loser.volatility = new_l

    for player, won in ((winner, True), (loser, False)):
        player.comparisons += 1
        if won:
            player.wins += 1
        else:
            player.losses += 1
        player.last_updated = now
