#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""
market.py — ADAAD Autonomous Marketing Engine
═══════════════════════════════════════════════════════════════════════════════

THE primary entry point for InnovativeAI LLC's autonomous exposure system.

This script is the reason this repo exists beyond the governance engine itself.
Every run discovers where ADAAD isn't yet visible, generates the right content
for that platform, and dispatches it — governed, logged, and repeatable.

USAGE:
  python market.py                     # full autonomous cycle (all eligible targets)
  python market.py --dry-run           # show what would be dispatched, no API calls
  python market.py --target devto      # run only Dev.to targets
  python market.py --target github     # update GitHub repo metadata
  python market.py --target prs        # open awesome-list PRs
  python market.py --discover          # use Claude to find NEW exposure opportunities
  python market.py --status            # print coverage report, no actions
  python market.py --queue             # print human-action queue (items needing Dustin)

ENVIRONMENT VARIABLES REQUIRED (set in GitHub Secrets):
  ANTHROPIC_API_KEY     — Claude API (powers discovery + content generation)
  GITHUB_TOKEN          — GitHub PAT (repo + public_repo scope)
  DEVTO_API_KEY         — Dev.to Forem API key
  REDDIT_CLIENT_ID      — Reddit OAuth app client ID
  REDDIT_CLIENT_SECRET  — Reddit OAuth app secret
  REDDIT_USERNAME       — Reddit account username
  REDDIT_PASSWORD       — Reddit account password

OPTIONAL:
  TWITTER_BEARER_TOKEN  — Twitter API v2 bearer token
  HASHNODE_TOKEN        — Hashnode Personal Access Token
  HASHNODE_PUB_ID       — Hashnode Publication (blog) ID
  MARKETING_DRY_RUN     — set to "true" to force dry-run mode

Constitutional invariant: Every dispatch is logged to marketing/state/
before any external API call completes. The log is append-only.
No platform is contacted without a passing policy gate evaluation.

Author: Dustin L. Reid · InnovativeAI LLC
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path

# Ensure project root on path
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from runtime.marketing.engine import AutonomousMarketingEngine, EngineConfig
from runtime.marketing.state  import MarketingStateStore

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("market")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="ADAAD Autonomous Marketing Engine",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--dry-run",   action="store_true", help="No API calls — show what would run")
    parser.add_argument("--target",    choices=["devto","github","prs","reddit","twitter","mastodon","discussions","hashnode","all"], default="all")
    parser.add_argument("--discover",  action="store_true", help="Use Claude to find new exposure targets")
    parser.add_argument("--status",    action="store_true", help="Print coverage report, no actions")
    parser.add_argument("--queue",     action="store_true", help="Print human-action queue")
    parser.add_argument("--verbose",   action="store_true")
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    dry_run = args.dry_run or os.environ.get("MARKETING_DRY_RUN", "").lower() == "true"

    cfg = EngineConfig(
        anthropic_api_key   = os.environ.get("ANTHROPIC_API_KEY", ""),
        github_token        = os.environ.get("GITHUB_TOKEN", ""),
        devto_api_key       = os.environ.get("DEVTO_API_KEY", ""),
        hashnode_token      = os.environ.get("HASHNODE_TOKEN", ""),
        hashnode_pub_id     = os.environ.get("HASHNODE_PUB_ID", ""),
        reddit_client_id    = os.environ.get("REDDIT_CLIENT_ID", ""),
        reddit_client_secret= os.environ.get("REDDIT_CLIENT_SECRET", ""),
        reddit_username     = os.environ.get("REDDIT_USERNAME", ""),
        reddit_password     = os.environ.get("REDDIT_PASSWORD", ""),
        twitter_bearer      = os.environ.get("TWITTER_BEARER_TOKEN", ""),
        mastodon_token      = os.environ.get("MASTODON_ACCESS_TOKEN", ""),
        mastodon_instance   = os.environ.get("MASTODON_INSTANCE", "fosstodon.org"),
        dry_run             = dry_run,
        state_dir           = str(ROOT / "marketing" / "state"),
        drafts_dir          = str(ROOT / "marketing" / "drafts"),
        human_queue_dir     = str(ROOT / "marketing" / "human_queue"),
    )

    engine = AutonomousMarketingEngine(cfg)

    # ── STATUS only ──────────────────────────────────────────────────────────
    if args.status:
        report = engine.status_report()
        print(json.dumps(report, indent=2))
        return 0

    # ── HUMAN QUEUE ──────────────────────────────────────────────────────────
    if args.queue:
        queue = engine.human_queue()
        print("\n╔══════════════════════════════════════════════════════════════╗")
        print(  "║   ADAAD MARKETING — HUMAN ACTION QUEUE                      ║")
        print(  "╚══════════════════════════════════════════════════════════════╝\n")
        if not queue:
            print("  ✅  Queue empty — all human-required items are complete or pending draft.\n")
        for i, item in enumerate(queue, 1):
            print(f"  [{i}] {item['title']}")
            print(f"      Platform: {item['platform']}")
            print(f"      Action:   {item['action']}")
            print(f"      Why:      {item['why']}")
            print(f"      Draft:    {item.get('draft_file', 'auto-generating...')}\n")
        return 0

    # ── DISCOVERY ────────────────────────────────────────────────────────────
    if args.discover:
        log.info("Running Claude-powered opportunity discovery...")
        new_targets = engine.discover_opportunities()
        log.info("Discovered %d new targets", len(new_targets))
        for t in new_targets:
            print(f"  + {t['name']} ({t['url']}) — score: {t.get('relevance_score', '?')}")
        return 0

    # ── MAIN CYCLE ───────────────────────────────────────────────────────────
    log.info("═══ ADAAD Autonomous Marketing Cycle ═══")
    log.info("  Mode:   %s", "DRY RUN" if dry_run else "LIVE")
    log.info("  Target: %s", args.target)
    log.info("  Time:   %s", time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime()))

    results = engine.run(target_filter=args.target)

    # Print summary
    print("\n╔══════════════════════════════════════════════════════════════╗")
    print(  "║   MARKETING CYCLE COMPLETE                                   ║")
    print(  "╚══════════════════════════════════════════════════════════════╝")
    print(f"  Dispatched:  {results['dispatched']}")
    print(f"  Succeeded:   {results['succeeded']}")
    print(f"  Failed:      {results['failed']}")
    print(f"  Skipped:     {results['skipped']} (rate-limited or needs human)")
    print(f"  New targets: {results.get('new_discovered', 0)}")
    print(f"  Coverage:    {results['coverage_pct']:.0f}% of known platforms reached\n")

    if results.get('live_urls'):
        print("  ✅  Live URLs this cycle:")
        for url in results['live_urls']:
            print(f"     → {url}")
        print()

    if results.get('human_queue_additions'):
        print(f"  📋  {len(results['human_queue_additions'])} item(s) added to human queue.")
        print("      Run `python market.py --queue` to see what needs your attention.\n")

    return 0 if results['failed'] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
