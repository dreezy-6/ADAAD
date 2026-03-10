# SPDX-License-Identifier: MIT
"""Autonomous Marketing Engine — ADAAD Phase 11, M11-03.

The central intelligence layer. Uses the Claude API to:
  1. Discover new exposure opportunities (trending topics, new lists, hot communities)
  2. Generate platform-optimised content tuned to current context
  3. Decide which targets to hit each cycle based on ROI + rate limits
  4. Orchestrate all dispatch agents
  5. Learn from past results (which content format performed, which didn't)

Every action passes the MarketingGate before dispatch.
Every result is persisted to marketing/state/ (committed to repo).

Author: Dustin L. Reid · InnovativeAI LLC
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
import urllib.request
import urllib.error
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from runtime.marketing.state import MarketingStateStore, MarketingAction, TargetState
from runtime.marketing.dispatchers import (
    GitHubMetaDispatcher,
    GitHubPRDispatcher,
    DevToDispatcher,
    RedditDispatcher,
    TwitterDispatcher,
    HumanQueueDispatcher,
    DispatchResult,
)

log = logging.getLogger("adaad.marketing.engine")

REPO_URL = "https://github.com/dreezy-6/ADAAD"

# ─── Config ─────────────────────────────────────────────────────────────────

@dataclass
class EngineConfig:
    anthropic_api_key:    str = ""
    github_token:         str = ""
    devto_api_key:        str = ""
    reddit_client_id:     str = ""
    reddit_client_secret: str = ""
    reddit_username:      str = ""
    reddit_password:      str = ""
    twitter_bearer:       str = ""
    dry_run:              bool = False
    state_dir:            str = "marketing/state"
    drafts_dir:           str = "marketing/drafts"
    human_queue_dir:      str = "marketing/human_queue"


# ─── Static content library ─────────────────────────────────────────────────
# Curated, policy-approved content. Claude can extend this dynamically.

ADAAD_PITCH = {
    "one_line":    "Three AI agents improve your code — constitutionally gated, every change auditable.",
    "tagline":     "AI That Improves Your Code. Constitutionally.",
    "repo":        REPO_URL,
    "quickstart":  f"git clone {REPO_URL} && cd ADAAD && python onboard.py",
    "founder":     "Dustin L. Reid",
    "company":     "InnovativeAI LLC",
}

# ── Awesome-list targets ─────────────────────────────────────────────────────

AWESOME_LIST_TARGETS = [
    {
        "target_id":       "awesome-ai-agents-pr",
        "upstream_owner":  "e2b-dev",
        "upstream_repo":   "awesome-ai-agents",
        "file_path":       "README.md",
        "section_marker":  "Coding",
        "addition_line":   f"- [ADAAD]({REPO_URL}) — Three Claude-powered agents (Architect/Dream/Beast) autonomously propose code mutations, compete via genetic algorithm, then pass a 16-rule constitutional gate. Deterministic replay + SHA-256 evidence ledger. Free, MIT.",
        "pr_title":        "feat: add ADAAD — constitutional multi-agent code mutation system",
        "pr_body":         f"ADAAD is an open-source multi-agent autonomous coding system with a strict constitutional governance gate.\n\n- 3 AI agents (Architect / Dream / Beast) compete on code improvements\n- Genetic algorithm + UCB1 bandit for candidate selection\n- 16-rule constitutional gate — one failure halts everything\n- Deterministic replay — every decision re-runs byte-identical\n- SHA-256 hash-chained evidence ledger\n- MIT licensed, free Community tier\n\nRepo: {REPO_URL}\nQuickstart: `python onboard.py` (90 seconds, dry-run by default)",
        "platform":        "github_pr",
        "min_interval_h":  0,   # one-shot
    },
    {
        "target_id":       "awesome-llm-apps-pr",
        "upstream_owner":  "Shubhamsaboo",
        "upstream_repo":   "awesome-llm-apps",
        "file_path":       "README.md",
        "section_marker":  "Coding",
        "addition_line":   f"- [ADAAD]({REPO_URL}) — Governed autonomous code mutation: 3 Claude agents compete, 16-rule constitutional gate approves. MIT, free tier.",
        "pr_title":        "feat: add ADAAD — constitutional AI coding agent system",
        "pr_body":         f"Adding ADAAD — an open-source system where 3 Claude-powered AI agents autonomously propose and compete on code improvements, governed by a strict constitutional gate.\n\nGitHub: {REPO_URL}\nLicense: MIT",
        "platform":        "github_pr",
        "min_interval_h":  0,
    },
    {
        "target_id":       "awesome-python-pr",
        "upstream_owner":  "vinta",
        "upstream_repo":   "awesome-python",
        "file_path":       "README.md",
        "section_marker":  "Code Analysis",
        "addition_line":   f"* [ADAAD]({REPO_URL}) - Autonomous code mutation with constitutional governance: three Claude agents + genetic algorithm + 16-rule policy gate.",
        "pr_title":        "Add ADAAD: constitutional AI code mutation (devtools)",
        "pr_body":         f"ADAAD is a Python autonomous code mutation system built on Claude.\n\n- 3 agents propose mutations, genetic algorithm ranks them\n- 16-rule constitutional gate — fail-closed\n- Deterministic replay verification\n- MIT, free tier, Python 3.11+\n\n{REPO_URL}",
        "platform":        "github_pr",
        "min_interval_h":  0,
    },
    # ── Phase 12 expansion targets ─────────────────────────────────────────
    {
        "target_id":       "awesome-selfhosted-pr",
        "upstream_owner":  "awesome-selfhosted",
        "upstream_repo":   "awesome-selfhosted",
        "file_path":       "README.md",
        "section_marker":  "Software Development - Testing",
        "addition_line":   f"- [ADAAD]({REPO_URL}) - Constitutional AI governance for autonomous code mutation. Three competing AI agents, 16-rule policy gate, cryptographic audit ledger, deterministic replay. ([Source Code]({REPO_URL})) `MIT` `Python`",
        "pr_title":        "Add ADAAD — self-hosted constitutional AI code mutation engine (MIT, Python)",
        "pr_body":         f"Adding ADAAD: a self-hosted autonomous code mutation system governed by a constitutional policy engine.\n\n**Why awesome-selfhosted:**\n- Fully self-hostable: runs on your hardware, no external data dependency beyond the Claude API\n- MIT licensed, Community tier free forever\n- No telemetry: the evidence ledger is append-only and stored in your own repo\n- Python 3.11+, single `python onboard.py` setup\n\n**What it does:**\n- 3 AI agents (Architect/Dream/Beast) compete to improve your codebase\n- Genetic algorithm ranks candidates; 16-rule constitutional gate approves or blocks\n- Every decision is SHA-256 hash-chained and deterministically replayable\n\nRepo: {REPO_URL}",
        "platform":        "github_pr",
        "min_interval_h":  0,
    },
    {
        "target_id":       "best-of-ml-python-pr",
        "upstream_owner":  "ml-tooling",
        "upstream_repo":   "best-of-ml-python",
        "file_path":       "README.md",
        "section_marker":  "Code Quality",
        "addition_line":   f"- <b><a href=\"{REPO_URL}\">ADAAD</a></b>  ⭐ - Constitutionally governed autonomous code mutation. Three Claude-powered agents compete via genetic algorithm; 16-rule policy gate is the sole approval authority. Deterministic replay. MIT.",
        "pr_title":        "Add ADAAD — constitutional AI code mutation to best-of-ml-python",
        "pr_body":         f"ADAAD is a production-grade Python system for governed autonomous code improvement.\n\nKey technical facts:\n- Multi-agent mutation pipeline (Architect / Dream / Beast personas)\n- BLX-alpha genetic algorithm with elite preservation and UCB1 bandit\n- 16-rule constitutional gate — fail-closed, architectural enforcement\n- SHA-256 hash-chained evidence ledger\n- Momentum gradient descent weight adaptation\n- Thompson sampling for non-stationary reward detection\n\nMIT. Python 3.11. Free Community tier. {REPO_URL}",
        "platform":        "github_pr",
        "min_interval_h":  0,
    },
    {
        "target_id":       "awesome-claude-models-pr",
        "upstream_owner":  "anthropics",
        "upstream_repo":   "anthropic-cookbook",
        "file_path":       "README.md",
        "section_marker":  "Agents",
        "addition_line":   f"- [ADAAD]({REPO_URL}) — Production multi-agent system: three Claude agents compete via genetic algorithm, governed by a 16-rule constitutional gate. Deterministic replay, SHA-256 audit ledger. MIT.",
        "pr_title":        "Add ADAAD — constitutional multi-agent Claude coding system to cookbook",
        "pr_body":         f"ADAAD is a production system demonstrating multi-agent Claude usage in a governed pipeline.\n\nClaude usage pattern:\n- Three distinct agent personas (Architect, Dream, Beast) each called with different system prompts\n- Responses scored by a genetic algorithm and ranked by fitness\n- Only constitutional-gate-approved mutations execute\n- Every API call is logged to an append-only evidence ledger\n\nReal-world demonstration of: multi-agent orchestration, structured output, governed tool use.\n\nMIT. {REPO_URL}",
        "platform":        "github_pr",
        "min_interval_h":  0,
    },
]

# ── Dev.to articles ───────────────────────────────────────────────────────

DEVTO_ARTICLES = [
    {
        "target_id":    "devto-intro",
        "title":        "We built a constitutional AI mutation engine — here's how it works",
        "tags":         ["ai", "python", "opensource", "devtools"],
        "min_interval_h": 720,
        "body_key":     "intro",
    },
    {
        "target_id":    "devto-governance",
        "title":        "How ADAAD's 16-rule constitutional gate stops autonomous AI from going wrong",
        "tags":         ["ai", "security", "governance", "python"],
        "min_interval_h": 720,
        "body_key":     "governance",
    },
    {
        "target_id":    "devto-saas",
        "title":        "From open-source to SaaS: how InnovativeAI monetized a governed AI tool",
        "tags":         ["saas", "startup", "indiehackers", "ai"],
        "min_interval_h": 720,
        "body_key":     "saas",
    },
]

# ── Reddit targets ─────────────────────────────────────────────────────────

REDDIT_TARGETS = [
    {
        "target_id":    "reddit-machinelearning",
        "subreddit":    "MachineLearning",
        "kind":         "self",
        "title":        "[P] ADAAD: constitutional AI governance for autonomous code mutation — open source, MIT",
        "min_interval_h": 2160,  # 90 days
    },
    {
        "target_id":    "reddit-python",
        "subreddit":    "Python",
        "kind":         "link",
        "title":        "I built a 3-agent governed code mutation system in Python — constitutional gate, genetic algorithm, deterministic replay",
        "min_interval_h": 2160,
    },
    {
        "target_id":    "reddit-programming",
        "subreddit":    "programming",
        "kind":         "link",
        "title":        "ADAAD — autonomous AI code agents governed by a constitutional policy engine (MIT, free)",
        "min_interval_h": 2160,
    },
    {
        "target_id":    "reddit-selfhosted",
        "subreddit":    "selfhosted",
        "kind":         "self",
        "title":        "ADAAD — self-hosted AI code mutation engine, one-click Railway/Docker deploy",
        "min_interval_h": 2160,
    },
]

# ── Human-queue targets ────────────────────────────────────────────────────

HUMAN_QUEUE_TARGETS = [
    {
        "target_id":    "hackernews-show-hn",
        "platform":     "Hacker News",
        "title":        "Show HN: ADAAD — AI agents that improve your code, constitutionally gated",
        "action":       "Submit manually at https://news.ycombinator.com/submit",
        "why":          "HN has no submission API. Must be Dustin's personal account for credibility. This is the single highest-ROI action.",
        "draft_file":   "hackernews_show_hn.md",
        "min_interval_h": 0,
    },
    {
        "target_id":    "producthunt-launch",
        "platform":     "Product Hunt",
        "title":        "ADAAD — Three AI agents. One governance gate. Zero unsupervised changes.",
        "action":       "Schedule launch at https://producthunt.com. Best day: Tue–Thu, 12:01am PST.",
        "why":          "Product Hunt drives thousands of developer eyeballs on launch day. Requires a PH account and 3–5 hunters lined up to upvote.",
        "draft_file":   "producthunt_launch.md",
        "min_interval_h": 0,
    },
    {
        "target_id":    "indiehackers-post",
        "platform":     "Indie Hackers",
        "title":        "I built ADAAD: governed AI code mutation — here's the founding story",
        "action":       "Post at https://www.indiehackers.com/post",
        "why":          "IH audience loves honest founder stories. Post monthly revenue milestones for maximum traction.",
        "draft_file":   "indiehackers_post.md",
        "min_interval_h": 0,
    },
]


# ─── Content generation via Claude API ──────────────────────────────────────

def _call_claude(api_key: str, prompt: str, max_tokens: int = 2000) -> str:
    """Call Claude API and return the text response."""
    if not api_key:
        return ""
    payload = {
        "model":      "claude-sonnet-4-20250514",
        "max_tokens": max_tokens,
        "messages":   [{"role": "user", "content": prompt}],
    }
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=json.dumps(payload).encode(),
        headers={
            "x-api-key":         api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type":      "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = json.loads(resp.read().decode())
            return body["content"][0]["text"]
    except Exception as exc:
        log.error("Claude API error: %s", exc)
        return ""


def _generate_devto_body(api_key: str, body_key: str) -> str:
    """Use Claude to generate a full Dev.to article body."""
    prompts = {
        "intro": f"""Write a complete, compelling Dev.to article introducing ADAAD.

FACTS (use only these — no fabrication):
- ADAAD = Autonomous Device-Anchored Adaptive Development
- Built by Dustin L. Reid, InnovativeAI LLC, Blackwell Oklahoma
- GitHub: {REPO_URL}
- 3 Claude-powered agents: Architect (structural), Dream (creative), Beast (performance)
- Genetic algorithm (BLX-alpha crossover) ranks mutation candidates
- 16-rule constitutional gate — one failure = full halt, no exceptions
- Deterministic replay — every decision re-runs byte-identical
- SHA-256 hash-chained evidence ledger — append-only
- Self-calibrating weights via momentum gradient descent
- Free Community (50 epochs/mo), Pro $49/mo (500 epochs), Enterprise $499/mo
- MIT license, Python 3.11.9, free Android companion app
- Quickstart: git clone {REPO_URL} && python onboard.py

REQUIREMENTS:
- Start with the problem, not a product pitch
- Include actual code examples (onboard.py, a governance gate example)
- Explain the constitutional gate in plain English
- End with clear CTA linking to the repo
- 1,200–1,800 words
- Markdown formatted for Dev.to
- NO claims like 'revolutionary', 'best in class', 'game changer'
- NO fabricated metrics (no 'X users', no 'Y% improvement' unless from real data)
- Must include: {REPO_URL}""",

        "governance": f"""Write a technical deep-dive Dev.to article about ADAAD's constitutional governance model.

FACTS: {json.dumps(ADAAD_PITCH)}
ADAAD repo: {REPO_URL}
The constitutional gate has 16 rules across 3 tiers: Sandbox, Stable, Production.
Rules include: test coverage preservation, evidence ledger integrity, SPDX headers, 
determinism contract, replay proof, human sign-off record, dependency lock, 
federation signature, constitutional rule immutability, changelog entry.

REQUIREMENTS:
- Technical, engineer-to-engineer tone
- Explain WHY constitutional (architectural) vs rule-based (config)
- Show what a governance record looks like (JSON example)
- Explain deterministic replay and why it matters
- 1,000–1,400 words, Markdown for Dev.to
- CTA at end: {REPO_URL}""",

        "saas": f"""Write a Dev.to article from Dustin Reid's perspective: building a SaaS on top of an open-source AI governance tool.

FACTS:
- InnovativeAI LLC, founded by Dustin L. Reid
- ADAAD is MIT licensed and fully open source
- SaaS tiers: Community (free), Pro ($49/mo), Enterprise ($499/mo)
- Built with Stripe for billing, FastAPI backend, constitutional gate always enforced
- The constitutional guarantee: paying more NEVER weakens governance

REQUIREMENTS:
- Honest founder journey tone (Indie Hackers style)
- Cover: the decision to open-source, the monetization model, why governance is the moat
- 800–1,200 words
- CTA: {REPO_URL}"""
    }
    return _call_claude(api_key, prompts.get(body_key, prompts["intro"]))


def _generate_reddit_body(api_key: str, target: dict) -> str:
    """Generate Reddit post body for a specific subreddit."""
    subreddit = target["subreddit"]
    prompt = f"""Write a Reddit post body for r/{subreddit} about ADAAD.

FACTS:
- ADAAD: 3 Claude-powered AI agents propose code mutations
- Constitutional gate: 16 rules, fail-closed, one failure = full halt
- Deterministic replay: every decision re-runs byte-identical
- SHA-256 hash-chained evidence ledger
- MIT license, free Community tier (50 epochs/month)
- Python 3.11.9
- GitHub: {REPO_URL}
- Quickstart: git clone {REPO_URL} && python onboard.py

Subreddit context for r/{subreddit}:
- MachineLearning: technical, research-focused, use [P] prefix for projects
- Python: Python-specific technical details, show interesting code
- programming: broad developer audience, focus on the problem solved
- selfhosted: self-hosting focus, Docker/Railway deploy angle

REQUIREMENTS:
- Match r/{subreddit} culture exactly (avoid sounding like marketing)
- 200–500 words
- Must include: {REPO_URL}
- NO shill-y language (no 'check it out!', 'would love feedback!')
- Be specific about what makes it technically interesting"""
    return _call_claude(api_key, prompt, 1000)


def _discover_new_targets(api_key: str) -> List[Dict]:
    """Use Claude to discover new exposure opportunities."""
    prompt = f"""You are the marketing intelligence system for ADAAD ({REPO_URL}).

ADAAD is: an open-source autonomous code mutation system with 3 AI agents, 
a constitutional governance gate, deterministic replay, and SHA-256 evidence ledger.
Target audience: developers, ML engineers, AI safety researchers, devops teams.

Your task: identify 5–10 NEW high-value platforms, communities, or lists where ADAAD
should appear but probably doesn't yet.

Consider:
- GitHub repos with 'awesome-' prefix related to AI agents, coding tools, governance
- Developer newsletters (TLDR, Bytes, Changelog, DevOps Weekly, etc.)  
- Podcast opportunities (Software Engineering Daily, Practical AI, etc.)
- Academic venues (arXiv cs.SE, cs.AI)
- Community forums (Lobsters, Tildes, HackerNews alternatives)
- Discord servers for AI/LLM developers
- Developer-focused YouTube channels
- Technical blogs that cover AI tooling

Respond ONLY with a JSON array. Each item:
{{
  "name": "Platform Name",
  "url": "https://...",
  "category": "newsletter|podcast|academic|community|youtube|blog|awesome_list",
  "relevance_score": 0.0-1.0,
  "estimated_monthly_reach": integer,
  "submission_strategy": "api|email|form|github_pr|manual",
  "notes": "brief description of why and how to submit"
}}"""
    raw = _call_claude(api_key, prompt, 2000)
    try:
        # Strip markdown fences if present
        clean = raw.strip()
        if clean.startswith("```"):
            clean = clean.split("```")[1]
            if clean.startswith("json"):
                clean = clean[4:]
        return json.loads(clean.strip())
    except Exception:
        return []


def _generate_human_draft(api_key: str, target: dict) -> str:
    """Generate a complete draft for a human-queue target."""
    tid = target["target_id"]
    if tid == "hackernews-show-hn":
        prompt = f"""Write a perfect Show HN submission for ADAAD.

FACTS: {json.dumps(ADAAD_PITCH)}
ADAAD: {REPO_URL}

REQUIREMENTS:
- Title MUST start with "Show HN:" — max 80 characters
- Comment body: 200–400 words, technical, founder tone
- Explain the interesting technical decision (constitutional gate architecture)
- Anticipate HN questions: why constitutional vs rule-based? how does replay work?
- NO hype, NO adjectives like 'amazing', 'revolutionary'
- Include quickstart command

Format your response as:
TITLE: [the title here]

COMMENT:
[the comment body here]"""

    elif tid == "producthunt-launch":
        prompt = f"""Write a complete Product Hunt launch brief for ADAAD.

FACTS: {json.dumps(ADAAD_PITCH)}
ADAAD: {REPO_URL}

Include:
1. Tagline (max 60 chars)
2. Description (500 chars)  
3. First comment from founder (300 words, honest story)
4. Topics to tag (5 max)
5. Launch day strategy (day, time, who to ask for support)"""

    else:  # indiehackers
        prompt = f"""Write an Indie Hackers post from Dustin Reid, founder of InnovativeAI LLC.

Topic: Building ADAAD — a governed autonomous AI coding system — from Blackwell, Oklahoma.

ADAAD: {REPO_URL}
Be honest about: the founding story, why governance matters, current traction, 
what's worked and what hasn't. IH audience loves authentic founder stories.
800–1,200 words."""

    return _call_claude(api_key, prompt, 2000)


# ─── Marketing Gate ──────────────────────────────────────────────────────────

class MarketingGate:
    """Pre-flight check before every dispatch.

    MARKETING-GOV-01: Every outbound action must pass this gate.
    """
    def __init__(self, store: MarketingStateStore):
        self._store = store

    def check(self, target_id: str, min_interval_h: float) -> tuple[bool, str]:
        elapsed = self._store.elapsed_since_last_action(target_id)
        if elapsed < min_interval_h:
            return False, f"rate-limited: {elapsed:.1f}h elapsed, need {min_interval_h}h"
        return True, "ok"


# ─── Main Engine ─────────────────────────────────────────────────────────────

class AutonomousMarketingEngine:
    """The central orchestrator.

    One call to run() executes the full autonomous marketing cycle:
      1. GitHub metadata update (topics, description)
      2. Dev.to article publication
      3. awesome-list PRs
      4. Reddit posts
      5. Twitter thread
      6. Human queue generation (HN, PH, IH drafts)
      7. Claude-powered discovery of new targets
    """

    def __init__(self, cfg: EngineConfig) -> None:
        self._cfg   = cfg
        self._store = MarketingStateStore(cfg.state_dir)
        self._gate  = MarketingGate(self._store)

        # Dispatchers
        self._gh_meta  = GitHubMetaDispatcher(cfg.github_token)
        self._gh_pr    = GitHubPRDispatcher(cfg.github_token)
        self._devto    = DevToDispatcher(cfg.devto_api_key)
        self._reddit   = RedditDispatcher(
            cfg.reddit_client_id, cfg.reddit_client_secret,
            cfg.reddit_username, cfg.reddit_password,
        )
        self._twitter  = TwitterDispatcher(cfg.twitter_bearer)
        self._hqueue   = HumanQueueDispatcher(cfg.human_queue_dir)

    # ── Public interface ────────────────────────────────────────────────────

    def run(self, target_filter: str = "all") -> Dict[str, Any]:
        results = {
            "dispatched": 0, "succeeded": 0, "failed": 0, "skipped": 0,
            "live_urls": [], "human_queue_additions": [],
            "new_discovered": 0, "coverage_pct": 0.0,
        }

        # Always run GitHub metadata (idempotent, fast, highest impact)
        if target_filter in ("all", "github"):
            self._run_github_meta(results)

        # Dev.to articles
        if target_filter in ("all", "devto"):
            self._run_devto(results)

        # Awesome-list PRs
        if target_filter in ("all", "prs"):
            self._run_awesome_prs(results)

        # Reddit
        if target_filter in ("all", "reddit"):
            self._run_reddit(results)

        # Twitter
        if target_filter in ("all", "twitter"):
            self._run_twitter(results)

        # Always generate human-queue drafts (no API calls, just file writes)
        self._run_human_queue(results)

        # Discovery — run Claude to find new targets
        if target_filter == "all" and self._cfg.anthropic_api_key:
            new = self.discover_opportunities()
            results["new_discovered"] = len(new)

        cov = self._store.coverage_report()
        results["coverage_pct"] = cov.get("coverage_pct", 0.0)
        return results

    def status_report(self) -> Dict[str, Any]:
        cov  = self._store.coverage_report()
        recent = [
            {"target_id": a.target_id, "success": a.success, "live_url": a.live_url}
            for a in self._store.recent_actions(10)
        ]
        return {"coverage": cov, "recent_actions": recent, "human_queue": self._hqueue.all_pending()}

    def human_queue(self) -> list:
        return self._hqueue.all_pending()

    def discover_opportunities(self) -> List[Dict]:
        if not self._cfg.anthropic_api_key:
            log.info("No ANTHROPIC_API_KEY — skipping discovery")
            return []
        log.info("Running Claude opportunity discovery...")
        targets = _discover_new_targets(self._cfg.anthropic_api_key)
        if targets:
            # Save to state
            import pathlib
            out = pathlib.Path(self._cfg.state_dir) / "discovered_targets.json"
            existing = json.loads(out.read_text()) if out.exists() else []
            merged = {t["url"]: t for t in existing}
            merged.update({t["url"]: t for t in targets})
            out.write_text(json.dumps(list(merged.values()), indent=2))
            log.info("Saved %d discovered targets", len(targets))
        return targets

    # ── GitHub metadata ─────────────────────────────────────────────────────

    def _run_github_meta(self, results: dict) -> None:
        if not self._cfg.github_token:
            log.warning("GITHUB_TOKEN not set — skipping GitHub metadata update")
            results["skipped"] += 2
            return

        for target_id, action_fn in [
            ("github-topics",      self._gh_meta.update_topics),
            ("github-description", self._gh_meta.update_description),
        ]:
            ok, reason = self._gate.check(target_id, min_interval_h=168)
            if not ok:
                log.info("Gate: %s — %s", target_id, reason)
                results["skipped"] += 1
                continue
            if self._cfg.dry_run:
                log.info("[DRY RUN] Would call %s", target_id)
                results["skipped"] += 1
                continue
            r = action_fn()
            self._record(target_id, "github_meta", "metadata", None, r, results)

    # ── Dev.to ──────────────────────────────────────────────────────────────

    def _run_devto(self, results: dict) -> None:
        if not self._cfg.devto_api_key:
            log.warning("DEVTO_API_KEY not set — skipping Dev.to")
            results["skipped"] += len(DEVTO_ARTICLES)
            return

        for article in DEVTO_ARTICLES:
            tid = article["target_id"]
            ok, reason = self._gate.check(tid, article["min_interval_h"])
            if not ok:
                log.info("Gate: %s — %s", tid, reason)
                results["skipped"] += 1
                continue
            if self._cfg.dry_run:
                log.info("[DRY RUN] Would publish Dev.to article: %s", article["title"])
                results["skipped"] += 1
                continue

            # Generate body with Claude (fallback to minimal stub)
            body = _generate_devto_body(self._cfg.anthropic_api_key, article["body_key"])
            if not body:
                body = f"# {article['title']}\n\n{ADAAD_PITCH['one_line']}\n\nRepo: {REPO_URL}"

            r = self._devto.publish(
                title=article["title"],
                body_markdown=body,
                tags=article["tags"],
            )
            self._record(tid, "devto", "article", article["title"], r, results)

    # ── Awesome-list PRs ────────────────────────────────────────────────────

    def _run_awesome_prs(self, results: dict) -> None:
        if not self._cfg.github_token:
            log.warning("GITHUB_TOKEN not set — skipping awesome-list PRs")
            results["skipped"] += len(AWESOME_LIST_TARGETS)
            return

        for t in AWESOME_LIST_TARGETS:
            tid = t["target_id"]
            ok, reason = self._gate.check(tid, t["min_interval_h"])
            if not ok:
                log.info("Gate: %s — %s", tid, reason)
                results["skipped"] += 1
                continue
            if self._cfg.dry_run:
                log.info("[DRY RUN] Would open PR: %s/%s", t["upstream_owner"], t["upstream_repo"])
                results["skipped"] += 1
                continue

            r = self._gh_pr.submit_to_awesome_list(
                upstream_owner=t["upstream_owner"],
                upstream_repo=t["upstream_repo"],
                file_path=t["file_path"],
                addition_line=t["addition_line"],
                section_marker=t["section_marker"],
                pr_title=t["pr_title"],
                pr_body=t["pr_body"],
                target_id=tid,
            )
            self._record(tid, "github_pr", "pr", t["pr_title"], r, results)

    # ── Reddit ──────────────────────────────────────────────────────────────

    def _run_reddit(self, results: dict) -> None:
        if not all([self._cfg.reddit_client_id, self._cfg.reddit_username]):
            log.warning("Reddit credentials not set — skipping Reddit")
            results["skipped"] += len(REDDIT_TARGETS)
            return

        for t in REDDIT_TARGETS:
            tid = t["target_id"]
            ok, reason = self._gate.check(tid, t["min_interval_h"])
            if not ok:
                log.info("Gate: %s — %s", tid, reason)
                results["skipped"] += 1
                continue
            if self._cfg.dry_run:
                log.info("[DRY RUN] Would post r/%s: %s", t["subreddit"], t["title"])
                results["skipped"] += 1
                continue

            body = _generate_reddit_body(self._cfg.anthropic_api_key, t)
            if not body:
                body = f"{ADAAD_PITCH['one_line']}\n\nRepo: {REPO_URL}"

            if t["kind"] == "link":
                r = self._reddit.submit_link(t["subreddit"], t["title"], REPO_URL)
            else:
                r = self._reddit.submit_text(t["subreddit"], t["title"], body)
            self._record(tid, "reddit", "post", t["title"], r, results)

    # ── Twitter ─────────────────────────────────────────────────────────────

    def _run_twitter(self, results: dict) -> None:
        if not self._cfg.twitter_bearer:
            results["skipped"] += 1
            return
        tid = "twitter-launch-thread"
        ok, reason = self._gate.check(tid, 168)
        if not ok:
            results["skipped"] += 1
            return
        if self._cfg.dry_run:
            log.info("[DRY RUN] Would post Twitter thread")
            results["skipped"] += 1
            return

        tweets = [
            f"🧵 We built an autonomous AI coding engine that can never bypass its own governance rules. Here's how it works: [1/7] {REPO_URL}",
            "Three Claude-powered agents — Architect 🏛️, Dream 💭, Beast 🐉 — continuously propose code improvements. They compete. A genetic algorithm ranks them. [2/7]",
            "The winners hit a Constitutional Gate: 16 rules, evaluated in order. ONE failure = full halt. No exceptions. No workarounds. Not config — architecture. [3/7]",
            "Every decision is SHA-256 hash-chained into an append-only evidence ledger. Every decision replays byte-identical. Divergence = halt. [4/7]",
            "Scoring weights self-calibrate via momentum gradient descent. The system learns which mutation types are worth making across epochs. [5/7]",
            f"Free forever (50 epochs/mo). Open source. MIT. Android app.\n\nQuickstart: `git clone {REPO_URL} && python onboard.py` [6/7]",
            f"Built by @DustinReid / InnovativeAI LLC from Blackwell, Oklahoma 🦅\n\nStar the repo if this is interesting: {REPO_URL} [7/7]\n\n#AI #OpenSource #Python #AutonomousAgents #AIGovernance",
        ]
        r = self._twitter.post_thread(tweets)
        self._record(tid, "twitter", "thread", "ADAAD Launch Thread", r, results)

    # ── Human queue ─────────────────────────────────────────────────────────

    def _run_human_queue(self, results: dict) -> None:
        for t in HUMAN_QUEUE_TARGETS:
            tid = t["target_id"]
            # Only queue if not already queued
            existing = next(
                (i for i in self._hqueue.all_pending() if i["target_id"] == tid), None
            )
            if existing:
                continue

            draft = _generate_human_draft(self._cfg.anthropic_api_key, t)
            if not draft:
                draft = f"# {t['title']}\n\n{ADAAD_PITCH['one_line']}\n\n{REPO_URL}"

            self._hqueue.enqueue(
                target_id=tid,
                platform=t["platform"],
                title=t["title"],
                action=t["action"],
                why=t["why"],
                draft_content=draft,
                draft_filename=t["draft_file"],
            )
            results["human_queue_additions"].append(tid)
            log.info("Human queue: drafted %s", tid)

    # ── Record helper ────────────────────────────────────────────────────────

    def _record(
        self,
        target_id: str,
        platform:  str,
        content_type: str,
        title: Optional[str],
        r: DispatchResult,
        results: dict,
    ) -> None:
        results["dispatched"] += 1
        action = MarketingAction(
            action_id=hashlib.sha256(
                f"{target_id}:{int(time.time())}".encode()
            ).hexdigest()[:16],
            target_id=target_id,
            platform=platform,
            content_type=content_type,
            title=title,
            success=r.success,
            live_url=r.live_url,
            error=r.error,
            dispatched_at=int(time.time()),
            dry_run=self._cfg.dry_run,
        )
        self._store.log_action(action)

        state = self._store.get_target(target_id) or TargetState(target_id, platform)
        if r.success:
            results["succeeded"] += 1
            if r.live_url:
                results["live_urls"].append(r.live_url)
                state.mark_live(r.live_url)
            else:
                state.mark_submitted()
        else:
            results["failed"] += 1
            state.mark_failed(r.error or "unknown error")
        self._store.upsert_target(state)
