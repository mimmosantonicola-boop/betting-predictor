"""
data/news_fetcher.py — Multi-source football news aggregator.

Sources:
  1. NewsAPI (newsapi.org)    — free: 100 req/day
  2. GNews API (gnews.io)     — free: 100 req/day
  3. BBC Sport (scraping)     — public, no limit
  4. LiveScore (scraping)     — injury/suspension news

Each article: {title, summary, url, source, published_at, team, competition}
"""

from __future__ import annotations

import os
import re
import time
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
}
_DELAY = 3.0
_last_scrape: float = 0.0


class NewsFetcher:
    """Aggregates football news from multiple free sources."""

    def __init__(self):
        self.news_api_key = os.getenv("NEWS_API_KEY", "")
        self.gnews_api_key = os.getenv("GNEWS_API_KEY", "")
        self.session = requests.Session()
        self.session.headers.update(_HEADERS)

    # ── Public API ────────────────────────────────────────────────────────────

    def get_match_news(
        self,
        home_team: str,
        away_team: str,
        competition: str,
        max_per_source: int = 5,
    ) -> list[dict]:
        """
        Fetch news relevant to an upcoming match.
        Returns articles sorted by recency, deduplicated.
        """
        queries = [
            f"{home_team} {away_team}",
            f"{home_team} injury news",
            f"{away_team} injury news",
            f"{competition} {home_team}",
        ]

        articles = []

        # NewsAPI
        if self.news_api_key:
            for q in queries[:2]:
                articles.extend(
                    self._newsapi(q, max_per_source)
                )

        # GNews
        if self.gnews_api_key:
            for q in queries[:2]:
                articles.extend(
                    self._gnews(q, max_per_source)
                )

        # BBC Sport (always)
        articles.extend(self._bbc_sport(home_team, max_per_source))
        articles.extend(self._bbc_sport(away_team, max_per_source))

        # LiveScore injury news
        articles.extend(self._livescore_injuries(home_team))
        articles.extend(self._livescore_injuries(away_team))

        return self._deduplicate_and_sort(articles)

    def get_team_news(self, team_name: str, max_articles: int = 10) -> list[dict]:
        """Fetch recent news for a single team."""
        articles = []

        if self.news_api_key:
            articles.extend(self._newsapi(team_name, max_articles))
        if self.gnews_api_key:
            articles.extend(self._gnews(team_name, max_articles))
        articles.extend(self._bbc_sport(team_name, max_articles))

        return self._deduplicate_and_sort(articles)[:max_articles]

    # ── Source: NewsAPI ───────────────────────────────────────────────────────

    def _newsapi(self, query: str, limit: int) -> list[dict]:
        try:
            resp = self.session.get(
                "https://newsapi.org/v2/everything",
                params={
                    "q": query,
                    "language": "en",
                    "sortBy": "publishedAt",
                    "pageSize": limit,
                    "apiKey": self.news_api_key,
                },
                timeout=10,
            )
            if resp.status_code == 426:
                logger.debug("NewsAPI: free tier limitation")
                return []
            resp.raise_for_status()
            data = resp.json()
            return [
                {
                    "title": a.get("title", ""),
                    "summary": (a.get("description") or "")[:300],
                    "url": a.get("url", ""),
                    "source": a.get("source", {}).get("name", "NewsAPI"),
                    "published_at": a.get("publishedAt", ""),
                    "image": a.get("urlToImage", ""),
                    "query": query,
                }
                for a in data.get("articles", [])
                if a.get("title") and "[Removed]" not in a.get("title", "")
            ]
        except Exception as e:
            logger.debug("NewsAPI failed for '%s': %s", query, e)
            return []

    # ── Source: GNews ─────────────────────────────────────────────────────────

    def _gnews(self, query: str, limit: int) -> list[dict]:
        try:
            resp = self.session.get(
                "https://gnews.io/api/v4/search",
                params={
                    "q": query,
                    "lang": "en",
                    "max": min(limit, 10),
                    "token": self.gnews_api_key,
                },
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()
            return [
                {
                    "title": a.get("title", ""),
                    "summary": (a.get("description") or "")[:300],
                    "url": a.get("url", ""),
                    "source": a.get("source", {}).get("name", "GNews"),
                    "published_at": a.get("publishedAt", ""),
                    "image": a.get("image", ""),
                    "query": query,
                }
                for a in data.get("articles", [])
                if a.get("title")
            ]
        except Exception as e:
            logger.debug("GNews failed for '%s': %s", query, e)
            return []

    # ── Source: BBC Sport ─────────────────────────────────────────────────────

    def _bbc_sport(self, team_name: str, limit: int) -> list[dict]:
        """Scrape BBC Sport search for team news."""
        global _last_scrape
        elapsed = time.time() - _last_scrape
        if elapsed < _DELAY:
            time.sleep(_DELAY - elapsed)

        slug = team_name.lower().replace(" ", "+")
        url = f"https://www.bbc.co.uk/sport/football/{slug}"
        try:
            resp = self.session.get(url, timeout=12)
            _last_scrape = time.time()
            if resp.status_code == 404:
                # Try BBC search
                return self._bbc_search(team_name, limit)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "lxml")
            articles = []
            for item in soup.select("article, [data-component='article']")[:limit]:
                title_el = item.find(["h3", "h2", "a"])
                link_el = item.find("a", href=True)
                desc_el = item.find("p")
                if not title_el:
                    continue
                title = title_el.get_text(strip=True)
                if len(title) < 10:
                    continue
                href = link_el["href"] if link_el else ""
                if href.startswith("/"):
                    href = "https://www.bbc.co.uk" + href
                articles.append({
                    "title": title,
                    "summary": desc_el.get_text(strip=True)[:300] if desc_el else "",
                    "url": href,
                    "source": "BBC Sport",
                    "published_at": "",
                    "image": "",
                    "query": team_name,
                })
            return articles
        except Exception as e:
            logger.debug("BBC Sport scrape failed for '%s': %s", team_name, e)
            return []

    def _bbc_search(self, query: str, limit: int) -> list[dict]:
        """BBC Sport search as fallback."""
        global _last_scrape
        elapsed = time.time() - _last_scrape
        if elapsed < _DELAY:
            time.sleep(_DELAY - elapsed)

        url = f"https://www.bbc.co.uk/search?q={query.replace(' ', '+')}&filter=sport"
        try:
            resp = self.session.get(url, timeout=12)
            _last_scrape = time.time()
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "lxml")
            articles = []
            for item in soup.select("li[class*='search-result'], article")[:limit]:
                title_el = item.find(["h1", "h2", "h3"])
                link_el = item.find("a", href=True)
                if not title_el or not link_el:
                    continue
                href = link_el["href"]
                if not href.startswith("http"):
                    href = "https://www.bbc.co.uk" + href
                articles.append({
                    "title": title_el.get_text(strip=True),
                    "summary": "",
                    "url": href,
                    "source": "BBC Sport",
                    "published_at": "",
                    "image": "",
                    "query": query,
                })
            return articles
        except Exception:
            return []

    # ── Source: LiveScore injuries ────────────────────────────────────────────

    def _livescore_injuries(self, team_name: str) -> list[dict]:
        """
        Scrape basic injury information from LiveScore.
        Returns pseudo-articles with injury summaries.
        """
        global _last_scrape
        elapsed = time.time() - _last_scrape
        if elapsed < _DELAY:
            time.sleep(_DELAY - elapsed)

        slug = re.sub(r"[^a-z0-9]", "-", team_name.lower()).strip("-")
        url = f"https://www.livescore.com/en/football/team/{slug}/injuries/"
        try:
            resp = self.session.get(url, timeout=12)
            _last_scrape = time.time()
            if resp.status_code != 200:
                return []
            soup = BeautifulSoup(resp.text, "lxml")

            players = []
            for row in soup.select("tr, [class*='player'], [class*='injury']")[:10]:
                name_el = row.find(["td", "span"], string=re.compile(r"[A-Z][a-z]+ [A-Z]"))
                status_el = row.find(string=re.compile(r"Out|Doubtful|Suspended", re.I))
                if name_el and status_el:
                    players.append(f"{name_el.get_text(strip=True)}: {status_el.strip()}")

            if players:
                return [{
                    "title": f"{team_name} — Injury Report",
                    "summary": "; ".join(players[:5]),
                    "url": url,
                    "source": "LiveScore",
                    "published_at": datetime.now(timezone.utc).isoformat(),
                    "image": "",
                    "query": team_name,
                    "is_injury_report": True,
                }]
        except Exception as e:
            logger.debug("LiveScore injury scrape failed for %s: %s", team_name, e)
        return []

    # ── Utilities ─────────────────────────────────────────────────────────────

    @staticmethod
    def _deduplicate_and_sort(articles: list[dict]) -> list[dict]:
        seen_titles: set[str] = set()
        unique = []
        for a in articles:
            key = re.sub(r"\s+", " ", a.get("title", "").lower().strip())[:60]
            if key and key not in seen_titles:
                seen_titles.add(key)
                unique.append(a)

        # Sort: injury reports first, then by date
        def sort_key(a: dict):
            is_injury = int(a.get("is_injury_report", False))
            pub = a.get("published_at", "")
            return (-is_injury, -(len(pub)))  # recent = longer ISO string

        return sorted(unique, key=sort_key)
