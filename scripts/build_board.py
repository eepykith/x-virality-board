#!/usr/bin/env python3
"""Build data.json (+ optional digest) from raw/<handle>.json public X post dumps.

raw/<handle>.json = the JSON returned by X get_users_posts
(exclude=retweets,replies; post.fields=created_at,public_metrics,referenced_tweets,attachments;
expansions=attachments.media_keys; media.fields=type). Public post data only.

Usage: python3 scripts/build_board.py [--digest PATH]
"""
import json, re, sys, statistics, collections
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
cfg = json.load(open(ROOT / "config/watchlist.json"))
TZ = ZoneInfo(cfg["timezone"]); MIN = cfg["min_views"]; STAR = cfg["star_views"]; WIN = cfg.get("window_hours", 48)
EXC = [k.lower() for k in cfg["exclude_keywords"]]
now = datetime.now(timezone.utc)
STOP = set("""a an the and or but if of to in on at for with from by as is are was were be been being it its this that these those
i you he she we they me my our your his her their them us not no so do does did done just than then there here what which who whom
how why when where all any can will would should could about into over out up down more most very also new now one two get got
has have had https t co amp rt via vs like today tonight just still even after before first last next only back much many some s re
ll ve d m don't it's i'm that's here's let's he's they're we're you're im dont""".split())

def excluded(text):
    t = text.lower()
    return any(re.search(r"\b" + re.escape(k) + r"\b", t) for k in EXC)

def keywords(text, n=5):
    t = re.sub(r"https?://\S+|@\w+", " ", text)
    words = [w.strip("'").lower() for w in re.findall(r"[A-Za-z0-9][A-Za-z0-9'\.\-]*[A-Za-z0-9]|#\w+", t)]
    words = [w for w in words if w not in STOP and len(w) > 2 and not w.isdigit()]
    tags = [w for w in words if w.startswith("#")]
    c = collections.Counter(words)
    return list(dict.fromkeys(tags + [w for w, _ in c.most_common(n)]))[:n]

def fmt(n): return f"{n/1e6:.1f}M" if n >= 1e6 else (f"{n/1e3:.1f}K" if n >= 1e3 else str(n))

accounts, posts = [], []
for a in cfg["accounts"]:
    h, topic = a["handle"], a["topic"]
    f = ROOT / "raw" / f"{h}.json"
    if not f.exists():
        accounts.append({"handle": h, "topic": topic, "missing": True}); continue
    d = json.load(open(f))
    media = {m["media_key"]: m["type"] for m in d.get("includes", {}).get("media", [])}
    ps = d.get("data", [])
    views = [p["public_metrics"].get("impression_count", 0) for p in ps]
    med = statistics.median(views) if views else 0
    accounts.append({"handle": h, "topic": topic, "median": med, "sample": len(ps)})
    for p in ps:
        ct = datetime.fromisoformat(p["created_at"].replace("Z", "+00:00"))
        age = (now - ct).total_seconds() / 3600
        if age > WIN or excluded(p["text"]): continue
        if any(r.get("type") == "replied_to" for r in p.get("referenced_tweets", [])): continue
        mt = sorted({media.get(k, "media") for k in p.get("attachments", {}).get("media_keys", [])})
        fmt_kind = ("quote" if any(r.get("type") == "quoted" for r in p.get("referenced_tweets", [])) else "standalone")
        fmt_kind += " + " + ("/".join(mt) if mt else "text")
        if p["text"].rstrip().endswith("?"): fmt_kind += " + question"
        pm = p["public_metrics"]; v = pm.get("impression_count", 0)
        posts.append({"handle": "@" + h, "name": h, "topic": topic, "url": f"https://x.com/{h}/status/{p['id']}",
            "status_url": p.get("url"), "text": p["text"], "views": v, "views_label": fmt(v),
            "median": med, "multiple": round(v / med, 2) if med else None, "age_hours": round(age, 1),
            "created_at": ct.astimezone(TZ).isoformat(), "likes": pm.get("like_count", 0), "reposts": pm.get("retweet_count", 0),
            "replies": pm.get("reply_count", 0), "bookmarks": pm.get("bookmark_count", 0), "format": fmt_kind,
            "keywords": keywords(p["text"])})

hits = sorted([p for p in posts if p["views"] >= MIN], key=lambda p: -(p["multiple"] or 0))
for p in hits:
    p["highlight"] = p["views"] >= STAR
    p["hook"] = p["text"][:280]
    p["video_tip"] = f"{p['topic']} · {p['age_hours']}h old · {p['multiple']}× median · {p['format']} · kw: {', '.join(p['keywords'])}"
TOPIC_RE = {"FSD/Tesla": r"tesla|fsd|robotaxi|cybercab|cybertruck|roadster|model [3ysx]|supercharg|autonom|waymo|zoox|software update|nhtsa|driverless",
            "Pokemon TCG": r"pok[eé]mon|tcg|booster|etb|elite trainer|\\bset\\b|card|pull|promo",
            "Apple": r"apple|iphone|ipad|macbook|\\bmac\\b|imac|vision pro|airpods|ios|watch"}
on_topic = lambda p: re.search(TOPIC_RE[p["topic"]], p["text"], re.I) is not None
hits = [p for p in hits if on_topic(p)]
breakouts = [p for p in hits if (p["multiple"] or 0) >= 1.5]
# keep topic diversity: best per topic first, then by multiple
seen, ordered = set(), []
for p in breakouts:
    if p["topic"] not in seen: seen.add(p["topic"]); ordered.append(p)
breakouts = ordered + [p for p in breakouts if p not in ordered]
cnt = collections.Counter(); capped = []
for p in breakouts:
    if cnt[p["handle"]] < 2: cnt[p["handle"]] += 1; capped.append(p)
breakouts = capped

kwc = collections.Counter(); kwtopic = {}
for p in hits:
    for k in p["keywords"]: kwc[k] += 1; kwtopic.setdefault(k, set()).add(p["topic"])
rising = [(k, c, sorted(kwtopic[k])) for k, c in kwc.most_common(12) if c >= 2][:10]
fmtstat = collections.defaultdict(list)
for p in posts:
    if p["multiple"] is not None: fmtstat[p["format"]].append(p["multiple"])
formats = sorted([(f, len(v), statistics.median(v)) for f, v in fmtstat.items()], key=lambda x: -x[2])

by_handle = collections.defaultdict(list)
for p in hits: by_handle[p["handle"]].append(p["views"])
roster = sorted([{"handle": h, "name": h[1:], "best": max(v), "total": sum(v), "hits": len(v)} for h, v in by_handle.items()], key=lambda r: -r["best"])
no_hits = []
for a in accounts:
    hh = "@" + a["handle"]
    if hh in by_handle: continue
    mine = [p["views"] for p in posts if p["handle"] == hh]
    no_hits.append({"handle": hh, "max_views": max(mine) if mine else 0,
        "reason": (f"No original in the last {WIN}h reached {MIN:,} views; highest observed was {max(mine):,}." if mine else f"No original posts in the last {WIN}h.")})

today = now.astimezone(TZ).date().isoformat()
data = {
    "title": f"X virality board — {today}", "date": today, "timezone": cfg["timezone"],
    "updated": now.astimezone(TZ).isoformat(timespec="seconds"),
    "brand_title": "Your X Virality Score", "brand_handle": "FSD · Pokemon TCG · Apple",
    "operator": {"handle": "", "name": "", "profile_url": ""},
    "ui": {"default_theme": "night"},
    "hits": hits, "hits_count": len(hits), "virals": [], "outsiders": [], "outsiders_count": 0,
    "patterns": [f"{k} ({c})" for k, c, _ in rising] + [f"{f}: {m:.2f}× median (n={n})" for f, n, m in formats[:4]],
    "no_hits": no_hits, "virals_window": f"last ~{WIN}h",
    "virals_narrative": "Watchlist-only board; outsider scan not enabled.", "narrative_synthesis": "",
    "day_roster": roster, "you_rank": None, "posts_scanned": len(posts),
    "accounts": [{k: v for k, v in a.items()} for a in accounts],
    "leaderboards": {"as_of": today, "tracking_start": today, "days_included": [today], "month_days_included": [today],
        "week": {"label": f"Rolling week · from {today}", "range": [today, today], "entries": roster},
        "month": {"label": f"{now.astimezone(TZ):%B %Y} · from {today}", "range": [today, today], "entries": roster}},
}
json.dump(data, open(ROOT / "data.json", "w"), indent=1, ensure_ascii=False)
print(f"posts in window: {len(posts)}, hits >= {MIN}: {len(hits)}, breakouts: {len(breakouts)}")

if "--digest" in sys.argv:
    out = Path(sys.argv[sys.argv.index("--digest") + 1])
    L = [f"# X watchlist digest — {out.stem.replace('digest-','')}", "",
         f"_Generated {now.astimezone(TZ):%Y-%m-%d %I:%M %p} PT from public X data. Window: last {WIN}h, originals only (no replies/reposts). Median = median views of each account's last ~25 originals._", "",
         "## 1. Breakout posts"]
    for i, p in enumerate(breakouts[:8], 1):
        why = f"{p['format']}; {p['likes']:,} likes, {p['reposts']:,} reposts, {p['bookmarks']:,} bookmarks, {p['replies']:,} replies"
        L += [f"{i}. {p['url']}", f"   - Handle: {p['handle']} · Topic: {p['topic']}",
              f"   - Views: {p['views']:,} · {p['multiple']}× account median ({int(p['median']):,}) · Age: {p['age_hours']}h",
              f"   - Hook: \"{p['text'][:160].replace(chr(10),' ')}\"", f"   - Why it hit: {p.get('why') or why}"]
    quiet = [t for t in cfg["topics"] if t not in {p["topic"] for p in breakouts}]
    if quiet: L += ["", f"_No on-topic breakout (>=1.5x median and >={MIN:,} views) in the window for: {', '.join(quiet)}._"]
    L += ["", "## 2. Rising keywords and topics"]
    L += [f"- **{k}** — in {c} of {len(hits)} 5K+ posts ({', '.join(t)})" for k, c, t in rising] or ["- No keyword repeated across 2+ hits."]
    L += ["", "## 3. Winning formats", "Median views multiple by format across all window originals:"]
    L += [f"- {f}: {m:.2f}× median (n={n})" for f, n, m in formats]
    out.write_text("\n".join(L) + "\n"); print("digest ->", out)
