# github-trending-daily

每日 04:00 自動抓取 GitHub Trending 過去 24 小時星星增加最多的專案，整理成日報寫入 Obsidian vault。

## Quick Start

```bash
pip install requests beautifulsoup4
python src/scraper.py        # 抓取 trending → data/trending-YYYY-MM-DD.json
python src/generate_daily.py # 產生日報 → Obsidian vault
```

## Schedule

由 Mavis cron 每天 04:00 (Asia/Taipei) 觸發。

## Output

- 原始資料：`data/trending-YYYY-MM-DD.json`
- 日報：`G:\我的雲端硬碟\000 工作記錄\Claude workspace\Obsidian\sources\github-trending\YYYY-MM-DD.md`
- 跑版紀錄：`logs/`

## Config

| Env var | Default | Description |
|---|---|---|
| `TOP_N` | 20 | 抓取 top N 專案 |
| `GITHUB_TRENDING_URL` | `https://github.com/trending?since=daily` | Trending URL |
| `VAULT_PATH` | `G:\我的雲端硬碟\000 工作記錄\Claude workspace\Obsidian` | Obsidian vault 根目錄 |
