"""
Generate daily GitHub Trending report and push to Obsidian vault.

Reads latest data/trending-YYYY-MM-DD.json, renders a Markdown file with
frontmatter, and writes it to:
    <VAULT>/sources/github-trending-YYYY-MM-DD.md

Run:
    python src/generate_daily.py
    VAULT_PATH=... python src/generate_daily.py
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

# --- Config -----------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
LOGS_DIR = PROJECT_ROOT / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_VAULT = r"G:\我的雲端硬碟\000 工作記錄\Claude workspace\Obsidian"
VAULT_PATH = Path(os.environ.get("VAULT_PATH", DEFAULT_VAULT))
# Sean keeps sources/ flat — no subfolders. Use topic-prefixed filename.
SOURCES_SUBDIR = Path("sources")


# --- Helpers ----------------------------------------------------------------


def find_today_snapshot() -> Path:
    today = datetime.now().strftime("%Y-%m-%d")
    p = DATA_DIR / f"trending-{today}.json"
    if p.exists():
        return p
    # fallback: pick newest trending-*.json
    candidates = sorted(DATA_DIR.glob("trending-*.json"), key=lambda x: x.name)
    if not candidates:
        raise FileNotFoundError(f"No trending-*.json found in {DATA_DIR}")
    return candidates[-1]


def render_markdown(payload: dict) -> str:
    repos = payload.get("repos", [])
    scraped_at = payload.get("scraped_at", "")
    source_url = payload.get("source_url", "")
    report_date = scraped_at[:10] if scraped_at else datetime.now().strftime("%Y-%m-%d")

    # Group by language for at-a-glance scan
    by_lang: dict[str, list[dict]] = {}
    for r in repos:
        lang = r.get("language") or "Unknown"
        by_lang.setdefault(lang, []).append(r)

    # Stats
    total_stars_today = sum(r.get("stars_today", 0) for r in repos)
    langs = sorted(by_lang.keys(), key=lambda k: (-len(by_lang[k]), k))

    lines: list[str] = []
    lines.append("---")
    lines.append(f"created: {report_date}")
    lines.append('tags: ["sources", "github", "trending", "daily"]')
    lines.append(f"source_url: \"{source_url}\"")
    lines.append(f"scraped_at: \"{scraped_at}\"")
    lines.append("---")
    lines.append("")
    lines.append(f"# GitHub Trending Daily — {report_date}")
    lines.append("")
    lines.append(f"> Past 24h stars gain ranking · Top {len(repos)} repos · 總星星 +{total_stars_today:,} today")
    lines.append("")
    lines.append(f"Source: {source_url}")
    lines.append("")

    # Summary stats
    lines.append("## 摘要")
    lines.append("")
    lines.append(f"- 收錄專案數：**{len(repos)}**")
    lines.append(f"- 過去 24h 總星星增加：**+{total_stars_today:,}**")
    lines.append(f"- 涵蓋語言數：**{len(langs)}**")
    if langs:
        top3 = ", ".join(f"**{l}** ({len(by_lang[l])})" for l in langs[:3])
        lines.append(f"- 前 3 語言：{top3}")
    lines.append("")

    # Full ranking table
    lines.append("## 完整榜單")
    lines.append("")
    lines.append("| # | Repo | 語言 | 描述 | ⭐ Total | 🔥 Today |")
    lines.append("|---|------|------|------|---------:|---------:|")
    for r in repos:
        rank = r.get("rank", "")
        name = r.get("full_name", "")
        url = r.get("url", "")
        lang = r.get("language", "—") or "—"
        desc = (r.get("description") or "").replace("|", "\\|").replace("\n", " ")
        if len(desc) > 110:
            desc = desc[:107] + "..."
        total = r.get("total_stars", 0)
        today_s = r.get("stars_today", 0)
        lines.append(
            f"| {rank} | [{name}]({url}) | {lang} | {desc} | {total:,} | +{today_s:,} |"
        )
    lines.append("")

    # By language sections
    lines.append("## 依語言分組")
    lines.append("")
    for lang in langs:
        items = by_lang[lang]
        lines.append(f"### {lang} ({len(items)})")
        lines.append("")
        for r in items:
            name = r.get("full_name", "")
            url = r.get("url", "")
            today_s = r.get("stars_today", 0)
            total = r.get("total_stars", 0)
            desc = r.get("description", "")
            if desc:
                lines.append(f"- **[{name}]({url})** — +{today_s:,} today / {total:,} total")
                lines.append(f"  {desc}")
            else:
                lines.append(
                    f"- **[{name}]({url})** — +{today_s:,} today / {total:,} total"
                )
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## 為什麼這些專案會出現在榜單？")
    lines.append("")
    lines.append("這個榜單由 GitHub 自動計算：根據 repo 在過去 24 小時內獲得的星星數排序。")
    lines.append("通常代表這些專案在這一天被大量討論、推爆、或在 Hacker News / Reddit / X 等平台被推廣。")
    lines.append("")
    lines.append("如何利用這份日報：")
    lines.append("")
    lines.append("- 快速掃一眼 `摘要` 區塊看今天技術圈的風向")
    lines.append("- 從 `依語言分組` 找你熟悉語言的新星專案")
    lines.append("- 看到有興趣的就點進去看 README，決定要不要深入研究")
    lines.append("")
    lines.append("> 這份日報是 raw source，尚未經過知識庫 ingest。要做摘要、標註、跨天比較，請 Obsidian LLM agent 處理。")
    lines.append("")

    return "\n".join(lines)


def main() -> int:
    log_path = LOGS_DIR / f"run-{datetime.now().strftime('%Y%m%d-%H%M%S')}.log"
    log_lines: list[str] = []

    def log(msg: str) -> None:
        print(msg)
        log_lines.append(msg)

    try:
        snapshot = find_today_snapshot()
        log(f"[generate] reading {snapshot}")
        payload = json.loads(snapshot.read_text(encoding="utf-8"))

        if not payload.get("repos"):
            log("[generate] ERROR: payload has no repos", file=sys.stderr)
            return 2

        md = render_markdown(payload)

        # Determine report date from scraped_at (fallback to file date)
        scraped_at = payload.get("scraped_at", "")
        report_date = scraped_at[:10] if scraped_at else datetime.now().strftime("%Y-%m-%d")

        # Build vault path
        out_dir = VAULT_PATH / SOURCES_SUBDIR
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"github-trending-{report_date}.md"

        if out_path.exists():
            log(f"[generate] WARN: {out_path} already exists — overwriting")

        out_path.write_text(md, encoding="utf-8")
        log(f"[generate] wrote {out_path} ({len(md)} bytes, {payload['count']} repos)")

        # also write to project output/ for sanity check
        output_copy = PROJECT_ROOT / "output" / out_path.name
        output_copy.parent.mkdir(parents=True, exist_ok=True)
        output_copy.write_text(md, encoding="utf-8")
        log(f"[generate] mirror at {output_copy}")

        log_path.write_text("\n".join(log_lines), encoding="utf-8")
        return 0

    except Exception as e:
        log(f"[generate] FAILED: {e}")
        log_path.write_text("\n".join(log_lines), encoding="utf-8")
        return 1


if __name__ == "__main__":
    sys.exit(main())
