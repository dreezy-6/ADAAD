# ADAAD Autonomous Marketing Engine

This folder is the operational core of ADAAD's self-marketing system.

---

## How It Works

```
python market.py
     │
     ├── runtime/marketing/engine.py   ← orchestration brain (uses Claude API)
     ├── runtime/marketing/dispatchers.py  ← platform API clients
     └── runtime/marketing/state.py    ← persists everything here
```

The engine runs on a GitHub Actions cron daily. Every run:

1. **Updates GitHub metadata** — topics, description, social links (GitHub API)
2. **Publishes to Dev.to** — full articles via Forem API (Claude writes the body)
3. **Opens PRs to awesome-* lists** — fork → branch → commit → PR (GitHub API)
4. **Posts to Reddit** — r/MachineLearning, r/Python, r/programming (Reddit OAuth2)
5. **Posts Twitter thread** — 7-tweet thread (Twitter API v2)
6. **Generates human-queue drafts** — HN, Product Hunt, Indie Hackers (Claude writes these)
7. **Discovers new targets** — Claude scans for new lists, communities, newsletters

---

## Folders

```
marketing/
├── state/
│   ├── targets.json          ← current status of every platform target
│   ├── actions.log           ← append-only JSONL of every action taken
│   └── discovered_targets.json  ← new targets found by Claude
│
├── drafts/
│   └── *.md                  ← auto-generated content (archived)
│
└── human_queue/
    ├── queue.json            ← index of items needing Dustin's attention
    ├── QUEUE_REPORT.md       ← human-readable queue report
    ├── hackernews_show_hn.md ← ready-to-post Show HN submission
    ├── producthunt_launch.md ← PH launch brief
    └── indiehackers_post.md  ← IH founder story post
```

---

## Run It

```bash
# Full cycle (all targets that are eligible)
python market.py

# Dry run (no API calls — see what would happen)
python market.py --dry-run

# Only GitHub metadata
python market.py --target github

# Only awesome-list PRs
python market.py --target prs

# See what needs Dustin's manual action
python market.py --queue

# Use Claude to find new exposure opportunities
python market.py --discover

# Current coverage report
python market.py --status
```

---

## Required Secrets (GitHub → Settings → Secrets)

| Secret | Purpose |
|---|---|
| `ANTHROPIC_API_KEY` | Claude API — content generation + discovery |
| `GITHUB_TOKEN` | Auto-provided by Actions — topics, PRs |
| `DEVTO_API_KEY` | Dev.to Forem API |
| `REDDIT_CLIENT_ID` | Reddit OAuth2 app |
| `REDDIT_CLIENT_SECRET` | Reddit OAuth2 app |
| `REDDIT_USERNAME` | Reddit account |
| `REDDIT_PASSWORD` | Reddit account |
| `TWITTER_BEARER_TOKEN` | Twitter API v2 |

---

## Human Queue

Some platforms have no posting API. The engine auto-generates perfect drafts
for these and adds them to `human_queue/`. Run `python market.py --queue`
to see what's waiting.

**Current items requiring Dustin:**
1. **Hacker News** — Show HN submission (highest ROI action, no API)
2. **Product Hunt** — Launch day submission
3. **Indie Hackers** — Founder story post

---

## Constitutional Guarantee

The marketing engine is governed by the same constitutional principle as the
rest of ADAAD:

> **MARKETING-GOV-01:** No platform is contacted without a passing policy gate
> evaluation. Content must not contain deceptive claims, must include a CTA URL,
> and must respect the minimum posting interval for each platform.

The engine respects platform rate limits. It never spams. It only posts
authentic content grounded in ADAAD's documented capabilities.
