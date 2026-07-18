"""
Pick Top 5 GitHub trending repos most suitable for content creation
(IG carousel / TikTok / Shorts topic selection).

Heuristic scoring:
  score = stars_today * 10 + keyword_matches * 100

Two outputs:
  1. IM-friendly short message (stdout, for cron session to relay to Sean)
  2. Full markdown report → Obsidian vault `queries/daily-pick-YYYY-MM-DD.md`

Run:
    python src/pick_topics.py
"""

import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

# Force UTF-8 stdout so emoji and CJK don't blow up on Windows cp950 console
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

# --- Config -----------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"

DEFAULT_VAULT = r"G:\我的雲端硬碟\000 工作記錄\Claude workspace\Obsidian"
VAULT_PATH = Path(os.environ.get("VAULT_PATH", DEFAULT_VAULT))
# Topic picks live alongside the full daily report in sources/github-trending/
# (they're derived from the same raw data — same source category, not a query)
SOURCES_SUBDIR = Path("sources") / "github-trending"

TOP_N = int(os.environ.get("TOPIC_PICK_N", "5"))

# Heuristic keywords — repos matching these are more likely good for
# AI/developer content. Lowercase, plain strings.
CONTENT_KEYWORDS = [
    "ai", "ml", "llm", "gpt", "claude", "agent", "agents", "copilot",
    "cursor", "codex", "rag", "embedding", "vector", "prompt",
    "workflow", "automation", "developer", "dev tool", "devtool",
    "coding", "ide", "code", "open source", "open-source", "self-host",
    "self-hosted", "productivity", "saas", "platform", "framework",
    "sdk", "api", "alternative", "mcp", "context", "llms",
    "rag", "transformer", "diffusion", "stable", "image", "video",
    "audio", "voice", "speech", "tts", "stt", "ocr", "vision",
    "robotics", "autonomous", "reasoning", "inference", "training",
    "fine-tun", "finetune", "openai", "anthropic", "gemini", "huggingface",
    "langchain", "llamaindex", "vector db", "weaviate", "pinecone",
    "chromadb", "qdrant", "ollama", "vllm", "transformer", "moe",
    "agentic", "tool use", "function call", "code review", "refactor",
    "test", "ci", "deploy", "docker", "kubernetes", "observability",
    "monitoring", "log", "debug", "profil", "benchmark",
    "front-end", "frontend", "back-end", "backend", "fullstack",
    "react", "vue", "svelte", "next", "nuxt", "remix", "astro",
    "tailwind", "css", "design", "ui", "ux",
    "terminal", "cli", "shell", "bash", "zsh", "tmux",
    "editor", "vim", "neovim", "emacs", "vscode",
    "browser", "tab", "extension", "plugin",
    "data", "database", "sql", "postgres", "mysql", "sqlite",
    "redis", "kafka", "queue", "worker", "cron", "scheduler",
    "scraper", "crawler", "spider", "parser",
    "security", "auth", "oauth", "jwt", "encryption", "vpn", "proxy",
    "network", "http", "grpc", "websocket", "graphql", "rest",
    "mobile", "ios", "android", "flutter", "react native", "swift", "kotlin",
    "game", "engine", "unity", "godot", "minecraft",
    "music", "audio", "midi", "synth",
    "3d", "render", "blender", "cad", "modeling",
    "blockchain", "crypto", "web3", "solidity", "ethereum", "bitcoin",
    "iot", "embedded", "arduino", "raspberry",
    "scientific", "research", "physics", "chemistry", "biology", "math",
    "education", "learn", "tutorial", "course", "book",
    "writing", "markdown", "note", "knowledge", "wiki", "obsidian",
    "task", "todo", "note-taking", "second brain",
    "chat", "messag", "email", "calendar", "scheduler",
    "search", "rag", "retrieval",
    "translate", "i18n", "l10n", "multilingual",
    "performance", "speed", "fast", "optim", "cache", "memo",
    "git", "diff", "merge", "branch",
    "test", "mock", "stub", "fixture", "snapshot",
    "doc", "documentation", "api doc", "sdk doc", "readme",
    "cli", "command", "terminal", "tui", "repl",
    "model", "training", "fine-tun", "pretrain",
]


# --- Helpers ----------------------------------------------------------------


def keyword_score(text: str) -> list[str]:
    """
    Return list of keywords that match in text.

    - Multi-word keywords (containing space or hyphen): plain substring match
    - Single-word keywords: word-boundary regex to avoid false positives
      like "ui" matching inside "build" or "log" matching inside "technologies"
    """
    t = text.lower()
    matches: list[str] = []
    for kw in CONTENT_KEYWORDS:
        if " " in kw or "-" in kw:
            if kw in t:
                matches.append(kw)
        else:
            if re.search(r"\b" + re.escape(kw) + r"\b", t):
                matches.append(kw)
    return matches


def score_repo(repo: dict) -> tuple[int, str, list[str]]:
    """
    Return (score, reason, matches) for ranking.
    Higher = better pick.
    """
    text = " ".join(
        [
            repo.get("full_name", ""),
            repo.get("description", ""),
            repo.get("language", ""),
        ]
    )
    matches = keyword_score(text)
    stars_today = repo.get("stars_today", 0)

    if matches:
        # bonus for keyword match
        score = stars_today * 10 + len(matches) * 100
        unique = sorted(set(matches))
        reason = f"匹配主題：{', '.join(unique[:4])}"
    else:
        # no keyword match — just rank by stars
        score = stars_today
        reason = "高關注度但主題較泛，可做延伸話題或觀察"
    return score, reason, matches


def pick_top_n(repos: list[dict], n: int) -> list[tuple[int, str, list[str], dict]]:
    scored = []
    for r in repos:
        s, reason, matches = score_repo(r)
        scored.append((s, reason, matches, r))
    scored.sort(key=lambda x: (-x[0], -x[3].get("stars_today", 0)))
    return scored[:n]


# --- Formatters -------------------------------------------------------------


def format_im_message(picks: list, report_date: str) -> str:
    lines = [f"🌟 Daily Topic Pick — {report_date}", ""]
    for i, (score, reason, matches, r) in enumerate(picks, 1):
        stars = r.get("stars_today", 0)
        name = r.get("full_name", "")
        desc = r.get("description", "")
        if len(desc) > 90:
            desc = desc[:87] + "..."
        lines.append(f"**{i}. {name}** (+{stars:,} today)")
        if desc:
            lines.append(f"   {desc}")
        lines.append(f"   → {reason}")
        lines.append(f"   {r.get('url', '')}")
        lines.append("")
    return "\n".join(lines).rstrip()


def format_markdown(
    picks: list,
    report_date: str,
    source_url: str,
    source_file: str,
) -> str:
    lines: list[str] = []
    lines.append("---")
    lines.append(f"created: {report_date}")
    lines.append('tags: ["sources", "github", "trending", "topic-pick", "daily"]')
    lines.append(f'source: "{source_file}"')
    lines.append(f'source_url: "{source_url}"')
    lines.append("---")
    lines.append("")
    lines.append(f"# Daily Topic Pick — {report_date}")
    lines.append("")
    lines.append(
        "> 從今日 GitHub Trending 挑出 5 個最適合做內容的專案（IG carousel / 短影片 / Threads 選題）"
    )
    lines.append("")
    lines.append("**選題邏輯：** 啟發式評分 = `stars_today × 10 + 關鍵字命中 × 100`，關鍵字涵蓋 AI/開發者工具/生產力等 Sean 內容方向")
    lines.append("")
    lines.append("## 精選 Top 5")
    lines.append("")

    for i, (score, reason, matches, r) in enumerate(picks, 1):
        stars = r.get("stars_today", 0)
        total = r.get("total_stars", 0)
        name = r.get("full_name", "")
        lang = r.get("language", "—") or "—"
        url = r.get("url", "")
        desc = r.get("description", "（無描述）")
        lines.append(f"### {i}. [{name}]({url})")
        lines.append("")
        lines.append(f"**語言：** {lang}  |  **+{stars:,} today** / {total:,} total  |  **評分：** {score:,}")
        lines.append("")
        lines.append(f"> {desc}")
        lines.append("")
        lines.append(f"**為什麼適合做選題：** {reason}")
        if matches:
            uniq = sorted(set(matches))
            lines.append(f"**匹配標籤：** `{'`, `'.join(uniq)}`")
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## 怎麼用這份精選")
    lines.append("")
    lines.append("- 每個專案都可以是一則 IG carousel / 短影片的主題")
    lines.append(f"- 完整 14 個專案請看 vault 內 `sources/github-trending/{report_date}.md`")
    lines.append("- 看到有興趣的就點進去看 README，判斷值不值得展開")
    lines.append("- 如果有想深挖的，跟 Mavis 講，直接生成 carousel 草稿")
    lines.append("")
    return "\n".join(lines)


# --- Main -------------------------------------------------------------------


def main() -> int:
    today = datetime.now().strftime("%Y-%m-%d")
    snapshot = DATA_DIR / f"trending-{today}.json"
    if not snapshot.exists():
        print(
            f"ERROR: {snapshot} not found — trending cron must run first (04:00)",
            file=sys.stderr,
        )
        return 1

    payload = json.loads(snapshot.read_text(encoding="utf-8"))
    repos = payload.get("repos", [])
    if not repos:
        print("ERROR: empty repos in snapshot", file=sys.stderr)
        return 2

    picks = pick_top_n(repos, TOP_N)
    source_url = payload.get("source_url", "")
    source_file = f"sources/github-trending/{today}.md"

    # Output 1: IM message (stdout) — for cron session to relay
    im_msg = format_im_message(picks, today)
    print("===IM_MESSAGE_START===")
    print(im_msg)
    print("===IM_MESSAGE_END===")
    print()

    # Output 2: full markdown → Obsidian vault (sources/github-trending/, alongside full daily report)
    md = format_markdown(picks, today, source_url, source_file)
    out_dir = VAULT_PATH / SOURCES_SUBDIR
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"daily-pick-{today}.md"
    out_path.write_text(md, encoding="utf-8")
    print(f"WROTE_VAULT: {out_path}")

    # Output 3: project mirror
    output_dir = PROJECT_ROOT / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    mirror = output_dir / f"daily-pick-{today}.md"
    mirror.write_text(md, encoding="utf-8")
    print(f"WROTE_MIRROR: {mirror}")

    # Output 4: 1-line summary for cron reply
    top1 = picks[0][3]
    print()
    print("===SUMMARY===")
    print(
        f"OK: picked {len(picks)} topics for {today}. "
        f"#1 = {top1.get('full_name', '?')} (+{top1.get('stars_today', 0):,} today). "
        f"vault = {out_path}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
