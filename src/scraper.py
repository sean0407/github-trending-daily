"""
GitHub Trending daily scraper.

Scrapes https://github.com/trending?since=daily (past 24h stars gain ranking)
and writes a JSON snapshot to data/trending-YYYY-MM-DD.json.

Run:
    python src/scraper.py            # scrape today, default top 20
    TOP_N=30 python src/scraper.py   # override top N
"""

import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

# --- Config -----------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_URL = "https://github.com/trending?since=daily"
TOP_N = int(os.environ.get("TOP_N", "20"))
URL = os.environ.get("GITHUB_TRENDING_URL", DEFAULT_URL)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

NUM_RE = re.compile(r"[\d,]+")


# --- Helpers ----------------------------------------------------------------


def parse_int(text: str) -> int:
    """Parse '1,068' / '527,842' → 1068 / 527842. Returns 0 on garbage."""
    if not text:
        return 0
    m = NUM_RE.search(text)
    if not m:
        return 0
    try:
        return int(m.group(0).replace(",", ""))
    except ValueError:
        return 0


def fetch_trending(url: str) -> str:
    """Fetch the trending page HTML with retry-on-5xx."""
    last_err = None
    for attempt in range(3):
        try:
            resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=20)
            if resp.status_code == 200:
                return resp.text
            if 500 <= resp.status_code < 600:
                last_err = f"HTTP {resp.status_code}"
                continue
            resp.raise_for_status()
        except requests.RequestException as e:
            last_err = str(e)
    raise RuntimeError(f"Failed to fetch {url} after 3 attempts: {last_err}")


def parse_trending(html: str, top_n: int) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    repos: list[dict] = []
    for article in soup.select("article.Box-row"):
        if len(repos) >= top_n:
            break

        # Repo URL + name
        h2_a = article.select_one("h2 a")
        if not h2_a or not h2_a.get("href"):
            continue
        href = h2_a["href"].strip()
        if not href.startswith("/"):
            continue
        full_name = href.lstrip("/")  # e.g. "owner/repo"
        url = f"https://github.com{href}"

        # Description (may be missing for some repos)
        desc_p = article.select_one("p")
        description = desc_p.get_text(strip=True) if desc_p else ""

        # Language
        lang_span = article.find("span", attrs={"itemprop": "programmingLanguage"})
        language = lang_span.get_text(strip=True) if lang_span else ""

        # Total stars + forks
        total_stars = 0
        forks = 0
        stars_link = article.select_one("a[href$='/stargazers']")
        if stars_link:
            total_stars = parse_int(stars_link.get_text(strip=True))
        forks_link = article.select_one("a[href$='/forks']")
        if forks_link:
            forks = parse_int(forks_link.get_text(strip=True))

        # Stars today
        stars_today = 0
        today_span = article.select_one("span.d-inline-block.float-sm-right")
        if today_span:
            stars_today = parse_int(today_span.get_text(strip=True))

        repos.append(
            {
                "rank": len(repos) + 1,
                "full_name": full_name,
                "url": url,
                "description": description,
                "language": language,
                "total_stars": total_stars,
                "stars_today": stars_today,
                "forks": forks,
            }
        )

    return repos


# --- Main -------------------------------------------------------------------


def main() -> int:
    today = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d")
    out_path = DATA_DIR / f"trending-{today}.json"

    print(f"[scraper] fetching {URL}")
    html = fetch_trending(URL)
    print(f"[scraper] html size: {len(html)} bytes")

    repos = parse_trending(html, TOP_N)
    print(f"[scraper] parsed {len(repos)} repos (top {TOP_N})")

    if not repos:
        print("[scraper] ERROR: parsed 0 repos — page structure may have changed", file=sys.stderr)
        return 2

    payload = {
        "scraped_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "source_url": URL,
        "top_n": TOP_N,
        "count": len(repos),
        "repos": repos,
    }
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[scraper] wrote {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
