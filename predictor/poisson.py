"""
predictor/poisson.py — Poisson models for scoreline and corner probabilities.

Uses xG data from FBref to estimate expected goals per team,
then applies independent Poisson distributions to compute the full
scoreline probability matrix (Dixon-Coles style attack/defense adjustment).

Also provides a corner model: total corners ~ Poisson(home_cpg + away_cpg).

No external dependencies beyond the standard library.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from football.models import TeamStats

# Empirical average xG per team per game, per competition
LEAGUE_AVG_XG: dict[str, float] = {
    "SA":    1.35,
    "CL":    1.40,
    "ECL":   1.30,
    "WC":    1.20,
    "WCQE":  1.25,
    "WCQA":  1.30,
    "WCQC":  1.20,
    "WCQAS": 1.15,
    "WCQAF": 1.10,
}
_DEFAULT_AVG_XG = 1.30

# Home teams score ~10% more than at a neutral venue
HOME_ADVANTAGE = 1.10

# Compute grid up to MAX_GOALS × MAX_GOALS
MAX_GOALS = 6


# ── Core math ──────────────────────────────────────────────────────────────────

def _poisson_pmf(k: int, lam: float) -> float:
    """P(X = k) for X ~ Poisson(lam). Returns 1.0 at k=0 if lam ≤ 0."""
    if lam <= 0:
        return 1.0 if k == 0 else 0.0
    return math.exp(-lam) * (lam ** k) / math.factorial(k)


# ── Result container ───────────────────────────────────────────────────────────

@dataclass
class PoissonResult:
    """Full output of the Poisson scoreline model."""

    lambda_home: float
    lambda_away: float
    # grid[h][a] = P(home scores h AND away scores a)
    grid: list[list[float]] = field(default_factory=list)

    # ── Derived market probabilities ──────────────────────────────────────────

    @property
    def most_likely_scoreline(self) -> str:
        best_h = best_a = 0
        best_p = 0.0
        for h in range(MAX_GOALS + 1):
            for a in range(MAX_GOALS + 1):
                if self.grid[h][a] > best_p:
                    best_p = self.grid[h][a]
                    best_h, best_a = h, a
        return f"{best_h}-{best_a}"

    @property
    def home_win_pct(self) -> float:
        return round(sum(
            self.grid[h][a]
            for h in range(MAX_GOALS + 1)
            for a in range(MAX_GOALS + 1)
            if h > a
        ) * 100, 1)

    @property
    def draw_pct(self) -> float:
        return round(sum(
            self.grid[h][a]
            for h in range(MAX_GOALS + 1)
            for a in range(MAX_GOALS + 1)
            if h == a
        ) * 100, 1)

    @property
    def away_win_pct(self) -> float:
        return round(100.0 - self.home_win_pct - self.draw_pct, 1)

    @property
    def over_2_5_pct(self) -> float:
        return round(sum(
            self.grid[h][a]
            for h in range(MAX_GOALS + 1)
            for a in range(MAX_GOALS + 1)
            if h + a > 2
        ) * 100, 1)

    @property
    def under_2_5_pct(self) -> float:
        return round(100.0 - self.over_2_5_pct, 1)

    @property
    def over_3_5_pct(self) -> float:
        return round(sum(
            self.grid[h][a]
            for h in range(MAX_GOALS + 1)
            for a in range(MAX_GOALS + 1)
            if h + a > 3
        ) * 100, 1)

    @property
    def under_3_5_pct(self) -> float:
        return round(100.0 - self.over_3_5_pct, 1)

    @property
    def btts_yes_pct(self) -> float:
        return round(sum(
            self.grid[h][a]
            for h in range(MAX_GOALS + 1)
            for a in range(MAX_GOALS + 1)
            if h > 0 and a > 0
        ) * 100, 1)

    @property
    def btts_no_pct(self) -> float:
        return round(100.0 - self.btts_yes_pct, 1)

    def top_scorelines(self, n: int = 8) -> list[list]:
        """Return the N most probable scorelines as [[score, pct], ...]."""
        items = [
            [f"{h}-{a}", round(self.grid[h][a] * 100, 1)]
            for h in range(MAX_GOALS + 1)
            for a in range(MAX_GOALS + 1)
        ]
        items.sort(key=lambda x: x[1], reverse=True)
        return items[:n]


# ── Main entry point ───────────────────────────────────────────────────────────

def compute_poisson(
    home_stats: TeamStats,
    away_stats: TeamStats,
    competition_code: str = "",
) -> PoissonResult:
    """
    Compute the Poisson scoreline probability grid.

    Attack/defense adjustment (Dixon-Coles style):
      λ_home = (home_attack / avg) × (away_defense / avg) × avg × home_advantage
      λ_away = (away_attack / avg) × (home_defense / avg) × avg

    Falls back from xG → goals_scored if xG data is unavailable.
    """
    avg = LEAGUE_AVG_XG.get(competition_code, _DEFAULT_AVG_XG)

    def best(xg: float, goals: float) -> float:
        return xg if xg > 0 else (goals if goals > 0 else avg)

    home_att = best(home_stats.xg_pg,  home_stats.goals_scored_pg)
    away_att = best(away_stats.xg_pg,  away_stats.goals_scored_pg)
    home_def = best(home_stats.xga_pg, home_stats.goals_conceded_pg)
    away_def = best(away_stats.xga_pg, away_stats.goals_conceded_pg)

    lambda_home = (home_att / avg) * (away_def / avg) * avg * HOME_ADVANTAGE
    lambda_away = (away_att / avg) * (home_def / avg) * avg

    # Clamp to realistic range
    lambda_home = max(0.20, min(lambda_home, 5.0))
    lambda_away = max(0.20, min(lambda_away, 5.0))

    grid = [
        [_poisson_pmf(h, lambda_home) * _poisson_pmf(a, lambda_away)
         for a in range(MAX_GOALS + 1)]
        for h in range(MAX_GOALS + 1)
    ]

    return PoissonResult(
        lambda_home=round(lambda_home, 2),
        lambda_away=round(lambda_away, 2),
        grid=grid,
    )


# ── Corner model ───────────────────────────────────────────────────────────────

# Empirical average total corners per game, per competition
LEAGUE_AVG_CORNERS: dict[str, float] = {
    "SA":    10.5,
    "CL":    10.0,
    "ECL":    9.5,
    "WC":     9.0,
    "WCQE":   9.5,
    "WCQA":   9.0,
    "WCQC":   9.0,
    "WCQAS":  9.0,
    "WCQAF":  8.5,
}
_DEFAULT_AVG_CORNERS = 10.0

@dataclass
class CornerResult:
    lambda_corners: float
    over_9_5_corners_pct: float
    under_9_5_corners_pct: float


def compute_corner_poisson(
    home_corners_pg: float,
    away_corners_pg: float,
    competition_code: str = "",
) -> CornerResult | None:
    """
    Estimate over/under 9.5 corners using a Poisson model on total corners.

    λ = home_corners_pg + away_corners_pg, adjusted toward the league average
    when per-team data is sparse (either value is zero → fall back to average).

    Returns None if no usable data is available.
    """
    if home_corners_pg <= 0 and away_corners_pg <= 0:
        return None

    avg = LEAGUE_AVG_CORNERS.get(competition_code, _DEFAULT_AVG_CORNERS)

    # If only one side has data, substitute the other with half the league avg
    h = home_corners_pg if home_corners_pg > 0 else avg / 2
    a = away_corners_pg if away_corners_pg > 0 else avg / 2

    lambda_total = max(0.5, h + a)

    # P(total corners ≤ 9) = sum_{k=0}^{9} Poisson(k | lambda_total)
    under_9_5 = sum(_poisson_pmf(k, lambda_total) for k in range(10))
    over_9_5  = 1.0 - under_9_5

    return CornerResult(
        lambda_corners=round(lambda_total, 2),
        over_9_5_corners_pct=round(over_9_5 * 100, 1),
        under_9_5_corners_pct=round(under_9_5 * 100, 1),
    )
