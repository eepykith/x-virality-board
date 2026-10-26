# Daily refresh (run ~7:00 AM PT, digest due by 7:30 AM PT)

Live: https://eepykith.github.io/x-virality-board/ · Repo: https://github.com/eepykith/x-virality-board
Local clone: /workspace/x-virality-board (gh on the box is logged in as eepykith).

## 1. Pull fresh public posts (agent step, `x` MCP namespace; limit 30 reads/min)
- IDs (stable, skip lookup): ChuckCook 14084713, AIDRIVR 1137314605422657537, NotATeslaApp 1321939345042001921,
  teslascope 1115375020782436353, DirtyTesLa 1118594454515003393, BLKMDL3 988975103785365504,
  TeslaNewswire 1691404385845116928, wholemars 1263491240336769026, SawyerMerritt 243013409,
  PokeGuardian 3387387106, PokeBeach 261562450, LeonhartYT 2898851303, PokeJungle 209088518,
  markgurman 15958614, 9to5mac 15944436, MKBHD 29873662
- For each: `x.get_users_posts` with
  `{"id": ID, "max_results": 25, "exclude": "retweets,replies", "post.fields": "created_at,public_metrics,referenced_tweets,attachments", "expansions": "attachments.media_keys", "media.fields": "type"}`
  (write_to_file), then save the JSON body (the line starting with `{"data"`) as `raw/<Handle>.json`.
  16 calls total; fits in one minute.

## 2. Build + digest + publish
```bash
cd /workspace/x-virality-board && bash scripts/refresh.sh      # date defaults to today PT
```
This runs `scripts/build_board.py` (writes data.json and /workspace/xmanager/inbox/digest-YYYY-MM-DD.md),
commits, and pushes; Pages rebuilds in ~1 min. Verify: `curl -s https://eepykith.github.io/x-virality-board/data.json | jq .date`

## Rules
- Public post data only; nothing about Jerry/X-Man files. No drafts.
- Exclusions (crypto, scalping, bots) live in config/watchlist.json `exclude_keywords`.
- Medians = median views of each account's last ~25 originals (sample, not all-time). Hits = >=5,000 views in 48h; ★ >=10,000.
  Digest breakouts = on-topic, >=1.5x median, max 2 per handle, best per topic first.
