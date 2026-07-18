# github-trending-daily

每日自動抓取 GitHub Trending 過去 24 小時星星增加最多的專案，整理成日報 + Top 5 選題推播到 Obsidian vault。

## Schedule

由 Mavis cron 每天觸發（Asia/Taipei）：

| 時間 | 工作 | 輸出 |
|---|---|---|
| 04:00 | 抓 trending + 產完整日報 | `vault/sources/github-trending-YYYY-MM-DD.md` |
| 04:30 | 挑 Top 5 選題 + 推播給 Sean | `vault/sources/github-trending-pick-YYYY-MM-DD.md` + IM 通知 |

## Quick Start

```bash
pip install requests beautifulsoup4
python src/scraper.py         # 抓 trending → data/trending-YYYY-MM-DD.json
python src/generate_daily.py  # 完整日報 → Obsidian sources/
python src/pick_topics.py     # Top 5 選題 → Obsidian queries/ + IM message to stdout
```

## 選題邏輯

`pick_topics.py` 用啟發式評分：

```
score = stars_today * 10 + keyword_matches * 100
```

關鍵字涵蓋 AI / 開發者工具 / 生產力方向（單字用 word boundary 避免假陽性，例如「ui」不會匹配到「build」）。

**為什麼這個適合做內容：** 每個專案都附「匹配主題」理由，Sean 一看就知道這個專案跟自己的內容方向有什麼關聯。

## Output

- 原始資料：`data/trending-YYYY-MM-DD.json`
- 完整日報：`G:\我的雲端硬碟\000 工作記錄\Claude workspace\Obsidian\sources\github-trending-YYYY-MM-DD.md`
- Top 5 選題：`G:\我的雲端硬碟\000 工作記錄\Claude workspace\Obsidian\sources\github-trending-pick-YYYY-MM-DD.md`
- 跑版紀錄：`logs/`

## Config

| Env var | Default | Description |
|---|---|---|
| `TOP_N` | 20 | scrape 抓取 top N 專案 |
| `TOPIC_PICK_N` | 5 | pick_topics 選 top N 個 |
| `GITHUB_TRENDING_URL` | `https://github.com/trending?since=daily` | Trending URL |
| `VAULT_PATH` | `G:\我的雲端硬碟\000 工作記錄\Claude workspace\Obsidian` | Obsidian vault 根目錄 |
