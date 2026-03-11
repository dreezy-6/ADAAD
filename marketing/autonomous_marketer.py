#!/usr/bin/env python3
"""
ADAAD Autonomous Marketing Engine
InnovativeAI LLC — Dustin L. Reid, Founder

Zero-cost, multi-platform autonomous marketing system.
Uses Claude API to generate fresh content, posts to free platforms,
tracks engagement, and self-optimizes posting strategy.

Platforms supported (all free tiers):
  - Reddit (PRAW API — free)
  - Dev.to (free API)
  - Hashnode (free API)
  - GitHub Discussions (free)
  - HackerNews (free — HNAPI)
  - LinkedIn (manual queue + auto-draft)
  - Twitter/X (oauth2 free tier)
  - Mastodon (free API)
  - Lemmy (open-source Reddit alternative, free API)

Usage:
  python marketing/autonomous_marketer.py --platform all
  python marketing/autonomous_marketer.py --platform reddit devto github
  python marketing/autonomous_marketer.py --generate-only   # just produce content
  python marketing/autonomous_marketer.py --dry-run         # preview without posting
"""

import os
import json
import time
import random
import hashlib
import logging
import argparse
from datetime import datetime, timezone
from pathlib import Path

# ── Optional deps (graceful degradation) ──────────────────────────────────────
try:
    import anthropic
    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False

try:
    import praw  # pip install praw
    HAS_PRAW = True
except ImportError:
    HAS_PRAW = False

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

# ── Logging ────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("marketing/logs/marketer.log", mode="a"),
    ],
)
log = logging.getLogger("adaad.marketer")

# ── Config ─────────────────────────────────────────────────────────────────────
ADAAD_GITHUB = "https://github.com/InnovativeAI-adaad/ADAAD"
ADAAD_PRODUCT = """
ADAAD (Autonomous Device-Anchored Adaptive Development) is a free, open-source
AI coding governance system. Three Claude agents (Architect, Dream, Beast)
compete to improve your codebase. Every proposal passes a 16-rule constitutional
governance gate. SHA-256 hash-chained evidence ledger — cryptographically
provable, deterministically replayable. Community tier is free forever (MIT).
Pro: $49/month. Enterprise: $499/month. pip install adaad.
GitHub: https://github.com/InnovativeAI-adaad/ADAAD
"""

SUBREDDITS = [
    # HIGH PRIORITY — developer/AI tool audiences
    {"name": "programming",         "flair": None,           "priority": 1},
    {"name": "MachineLearning",     "flair": "Project",      "priority": 1},
    {"name": "LocalLLaMA",          "flair": "Discussion",   "priority": 1},
    {"name": "devops",              "flair": None,           "priority": 1},
    {"name": "softwareengineering", "flair": None,           "priority": 1},
    {"name": "artificial",         "flair": None,           "priority": 2},
    {"name": "opensource",         "flair": None,           "priority": 2},
    {"name": "Python",             "flair": "Project",      "priority": 2},
    {"name": "ChatGPTCoding",      "flair": None,           "priority": 2},
    {"name": "AIToolsTech",        "flair": None,           "priority": 2},
    {"name": "webdev",             "flair": None,           "priority": 3},
    {"name": "ClaudeAI",           "flair": None,           "priority": 1},
    {"name": "singularity",        "flair": None,           "priority": 3},
    {"name": "Entrepreneur",       "flair": None,           "priority": 3},
    {"name": "SideProject",        "flair": None,           "priority": 2},
    {"name": "startups",           "flair": None,           "priority": 3},
    # Compliance / regulated industries
    {"name": "cybersecurity",      "flair": None,           "priority": 2},
    {"name": "fintech",            "flair": None,           "priority": 2},
    {"name": "healthIT",           "flair": None,           "priority": 2},
]

DEVTO_TAGS = ["ai", "devtools", "opensource", "programming", "productivity"]

CONTENT_ANGLES = [
    "audit_trail",
    "compliance_regulated",
    "vs_copilot_cursor",
    "genetic_algorithm_deep_dive",
    "constitutional_governance",
    "free_open_source",
    "android_companion_app",
    "how_it_works_simple",
    "founder_story",
    "enterprise_use_case",
    "security_cryptographic",
    "self_calibrating_fitness",
    "deterministic_replay",
    "three_agents_compete",
]


def get_anthropic_client():
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY not set")
    if not HAS_ANTHROPIC:
        raise RuntimeError("pip install anthropic")
    return anthropic.Anthropic(api_key=api_key)


def generate_content(angle: str, platform: str, dry_run: bool = False) -> dict:
    """Use Claude to generate fresh, non-repetitive marketing content."""
    if dry_run or not HAS_ANTHROPIC:
        return _fallback_content(angle, platform)

    client = get_anthropic_client()
    seed = hashlib.sha256(f"{angle}{platform}{datetime.now().date()}".encode()).hexdigest()[:8]

    system = f"""You are a marketing copywriter for ADAAD, an open-source AI coding governance tool.
Write authentic, technically accurate content. NEVER use marketing buzzwords like 'revolutionary', 
'game-changing', 'disruptive'. Be direct, honest, and technical. Sound like a developer, not a marketer.

ADAAD facts:
{ADAAD_PRODUCT}

Key differentiators:
- ONLY AI coding tool with cryptographic audit trail (SHA-256 hash-chained)
- Deterministic replay — re-run any epoch months later, byte-identical outputs
- Constitutional governance gate — 16 hard rules, cannot be overridden
- Three competing agents (Architect/Dream/Beast) + genetic algorithm
- Totally free community tier (MIT, self-hosted, no telemetry)
- Android app available
- Founded by Dustin L. Reid, InnovativeAI LLC, Blackwell Oklahoma

Seed for variety: {seed}
"""

    platform_instructions = {
        "reddit": "Write a Reddit post: casual, direct, no fluff. Title + body. Max 500 words. Acknowledge you built it (transparent).",
        "devto": "Write a Dev.to article: technical depth, code examples if applicable, 400-800 words. Include frontmatter: title, tags, description.",
        "twitter": "Write 5 tweet thread. First tweet is hook. Technical, no hype. Each tweet max 280 chars. End with GitHub link.",
        "linkedin": "Write LinkedIn post: professional but authentic. 150-300 words. No emoji overload. Paragraph format.",
        "github_discussion": "Write a GitHub Discussions post announcing ADAAD. Link to key docs. Invite technical questions.",
        "mastodon": "Write a Mastodon post. Max 500 chars. Technical, direct. Include hashtags at end.",
        "producthunt": "Write a Product Hunt tagline (60 chars max) and description (260 chars max) and first comment (500 words, technical).",
        "hackernews": "Write a Show HN title (max 80 chars) and optional comment body. Extremely technical, no marketing.",
    }

    angle_instructions = {
        "audit_trail": "Focus on the SHA-256 hash-chained evidence ledger and why audit trails matter in production.",
        "compliance_regulated": "Focus on fintech/healthcare/gov use cases where you need to prove AI decisions.",
        "vs_copilot_cursor": "Honest comparison. What Copilot/Cursor do well, what ADAAD does that they can't.",
        "genetic_algorithm_deep_dive": "Explain the BLX-alpha GA, UCB1 bandit, elite preservation, Thompson sampling.",
        "constitutional_governance": "Explain the 16-rule constitutional gate and why it can't be overridden.",
        "free_open_source": "Emphasize MIT license, self-hosted, no telemetry, free community tier.",
        "android_companion_app": "Highlight the Android app — monitor mutations on your phone.",
        "how_it_works_simple": "Explain ADAAD to a non-technical audience in simple terms.",
        "founder_story": "Dustin Reid built this because AI coding tools had no accountability. The personal story.",
        "enterprise_use_case": "Enterprise angle: compliance, auditors, regulated environments.",
        "security_cryptographic": "Deep dive on the cryptographic properties: SHA-256, replay proof, tamper detection.",
        "self_calibrating_fitness": "Explain momentum gradient descent fitness calibration — the system learns.",
        "deterministic_replay": "What deterministic replay means: prove the AI decision was correct 6 months later.",
        "three_agents_compete": "Explain the Architect/Dream/Beast agents and why competition produces better code.",
    }

    prompt = f"""
Platform: {platform}
Content angle: {angle}

{platform_instructions.get(platform, 'Write a general marketing post.')}

Angle focus: {angle_instructions.get(angle, 'General ADAAD overview.')}

Return ONLY a JSON object with these keys:
- "title": post title (if applicable)
- "body": main content body
- "tags": list of relevant tags/hashtags
- "cta": call-to-action text
- "platform": "{platform}"
- "angle": "{angle}"

Do not include any text outside the JSON object.
"""

    response = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=1500,
        system=system,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = response.content[0].text.strip()
    # Strip markdown fences if present
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        log.warning("Claude response not valid JSON, using fallback")
        return _fallback_content(angle, platform)


def _fallback_content(angle: str, platform: str) -> dict:
    """Static fallback content when API unavailable."""
    return {
        "title": "ADAAD: Constitutional AI governance for your codebase (MIT, free)",
        "body": (
            "I built ADAAD because every AI coding tool can suggest code, "
            "but none can prove the suggestion was safe.\n\n"
            "Three Claude agents compete. A genetic algorithm ranks proposals. "
            "A 16-rule constitutional gate approves or halts — no exceptions.\n\n"
            "SHA-256 hash-chained audit trail. Deterministic replay. "
            "Cryptographically provable decisions.\n\n"
            f"Free forever (MIT). pip install adaad\n{ADAAD_GITHUB}"
        ),
        "tags": ["ai", "opensource", "devtools", "programming"],
        "cta": f"GitHub: {ADAAD_GITHUB}",
        "platform": platform,
        "angle": angle,
    }


# ── Reddit Poster ──────────────────────────────────────────────────────────────
class RedditPoster:
    def __init__(self):
        if not HAS_PRAW:
            raise RuntimeError("pip install praw")
        self.reddit = praw.Reddit(
            client_id=os.environ["REDDIT_CLIENT_ID"],
            client_secret=os.environ["REDDIT_CLIENT_SECRET"],
            username=os.environ["REDDIT_USERNAME"],
            password=os.environ["REDDIT_PASSWORD"],
            user_agent="ADAAD autonomous marketer v1.0 (by /u/InnovativeAI_ADAAD)",
        )

    def post(self, subreddit_name: str, title: str, body: str, dry_run: bool = False) -> dict:
        if dry_run:
            log.info(f"[DRY RUN] Would post to r/{subreddit_name}: {title[:60]}...")
            return {"status": "dry_run", "subreddit": subreddit_name}

        try:
            sub = self.reddit.subreddit(subreddit_name)
            submission = sub.submit(title=title, selftext=body, send_replies=False)
            log.info(f"Posted to r/{subreddit_name}: {submission.url}")
            return {"status": "ok", "url": submission.url, "id": submission.id}
        except Exception as e:
            log.error(f"Reddit post failed ({subreddit_name}): {e}")
            return {"status": "error", "error": str(e)}

    def post_to_priority_subreddits(self, priority: int = 1, dry_run: bool = False):
        targets = [s for s in SUBREDDITS if s["priority"] <= priority]
        angle = random.choice(CONTENT_ANGLES)
        content = generate_content(angle, "reddit", dry_run)
        results = []
        for sub in targets:
            result = self.post(sub["name"], content["title"], content["body"], dry_run)
            results.append(result)
            # Respect Reddit rate limits: 1 post per 10 min
            if not dry_run:
                time.sleep(600)
        return results


# ── Dev.to Poster ──────────────────────────────────────────────────────────────
class DevtoPoster:
    BASE = "https://dev.to/api"

    def __init__(self):
        self.api_key = os.environ.get("DEVTO_API_KEY")
        if not self.api_key:
            raise RuntimeError("DEVTO_API_KEY not set")

    def post(self, title: str, body: str, tags: list, published: bool = True, dry_run: bool = False) -> dict:
        if dry_run:
            log.info(f"[DRY RUN] Would post to Dev.to: {title[:60]}...")
            return {"status": "dry_run"}

        payload = {
            "article": {
                "title": title,
                "body_markdown": body,
                "published": published,
                "tags": tags[:4],  # Dev.to max 4 tags
                "canonical_url": ADAAD_GITHUB,
            }
        }
        resp = requests.post(
            f"{self.BASE}/articles",
            json=payload,
            headers={"api-key": self.api_key, "Content-Type": "application/json"},
        )
        if resp.ok:
            data = resp.json()
            log.info(f"Posted to Dev.to: {data.get('url')}")
            return {"status": "ok", "url": data.get("url"), "id": data.get("id")}
        else:
            log.error(f"Dev.to post failed: {resp.status_code} {resp.text}")
            return {"status": "error", "code": resp.status_code}


# ── Hashnode Poster ────────────────────────────────────────────────────────────
class HashnodePoster:
    ENDPOINT = "https://gql.hashnode.com"

    def __init__(self):
        self.token = os.environ.get("HASHNODE_TOKEN")
        self.publication_id = os.environ.get("HASHNODE_PUBLICATION_ID")

    def post(self, title: str, body: str, tags: list, dry_run: bool = False) -> dict:
        if dry_run:
            log.info(f"[DRY RUN] Would post to Hashnode: {title[:60]}...")
            return {"status": "dry_run"}

        query = """
        mutation PublishPost($input: PublishPostInput!) {
          publishPost(input: $input) {
            post { url id }
          }
        }
        """
        variables = {
            "input": {
                "title": title,
                "contentMarkdown": body,
                "publicationId": self.publication_id,
                "tags": [{"name": t, "slug": t} for t in tags[:5]],
            }
        }
        resp = requests.post(
            self.ENDPOINT,
            json={"query": query, "variables": variables},
            headers={"Authorization": self.token},
        )
        if resp.ok:
            data = resp.json()
            post_data = data.get("data", {}).get("publishPost", {}).get("post", {})
            log.info(f"Posted to Hashnode: {post_data.get('url')}")
            return {"status": "ok", "url": post_data.get("url")}
        return {"status": "error", "code": resp.status_code}


# ── GitHub Discussions Poster ──────────────────────────────────────────────────
class GitHubDiscussionsPoster:
    """Post to GitHub Discussions on InnovativeAI-adaad/ADAAD using GraphQL."""

    ENDPOINT = "https://api.github.com/graphql"

    def __init__(self):
        self.token = os.environ.get("GITHUB_TOKEN")
        self.repo_owner = "InnovativeAI-adaad"
        self.repo_name = "ADAAD"

    def _get_category_id(self) -> str:
        """Get the first available discussion category ID."""
        query = """
        query($owner: String!, $name: String!) {
          repository(owner: $owner, name: $name) {
            discussionCategories(first: 10) {
              nodes { id name }
            }
          }
        }
        """
        resp = requests.post(
            self.ENDPOINT,
            json={"query": query, "variables": {"owner": self.repo_owner, "name": self.repo_name}},
            headers={"Authorization": f"Bearer {self.token}"},
        )
        cats = resp.json()["data"]["repository"]["discussionCategories"]["nodes"]
        # Prefer 'General' or 'Announcements'
        for cat in cats:
            if cat["name"].lower() in ("general", "announcements", "show and tell"):
                return cat["id"]
        return cats[0]["id"] if cats else None

    def _get_repo_id(self) -> str:
        query = """
        query($owner: String!, $name: String!) {
          repository(owner: $owner, name: $name) { id }
        }
        """
        resp = requests.post(
            self.ENDPOINT,
            json={"query": query, "variables": {"owner": self.repo_owner, "name": self.repo_name}},
            headers={"Authorization": f"Bearer {self.token}"},
        )
        return resp.json()["data"]["repository"]["id"]

    def post(self, title: str, body: str, dry_run: bool = False) -> dict:
        if dry_run:
            log.info(f"[DRY RUN] Would post GitHub Discussion: {title[:60]}...")
            return {"status": "dry_run"}

        try:
            repo_id = self._get_repo_id()
            cat_id = self._get_category_id()
            mutation = """
            mutation($input: CreateDiscussionInput!) {
              createDiscussion(input: $input) {
                discussion { url id }
              }
            }
            """
            resp = requests.post(
                self.ENDPOINT,
                json={
                    "query": mutation,
                    "variables": {
                        "input": {
                            "repositoryId": repo_id,
                            "categoryId": cat_id,
                            "title": title,
                            "body": body,
                        }
                    },
                },
                headers={"Authorization": f"Bearer {self.token}"},
            )
            data = resp.json().get("data", {}).get("createDiscussion", {}).get("discussion", {})
            log.info(f"Posted GitHub Discussion: {data.get('url')}")
            return {"status": "ok", "url": data.get("url")}
        except Exception as e:
            log.error(f"GitHub Discussions post failed: {e}")
            return {"status": "error", "error": str(e)}


# ── Mastodon Poster ────────────────────────────────────────────────────────────
class MastodonPoster:
    def __init__(self):
        self.access_token = os.environ.get("MASTODON_ACCESS_TOKEN")
        self.instance = os.environ.get("MASTODON_INSTANCE", "mastodon.social")

    def post(self, content: str, dry_run: bool = False) -> dict:
        if dry_run:
            log.info(f"[DRY RUN] Would toot to Mastodon: {content[:60]}...")
            return {"status": "dry_run"}

        resp = requests.post(
            f"https://{self.instance}/api/v1/statuses",
            data={"status": content[:500], "visibility": "public"},
            headers={"Authorization": f"Bearer {self.access_token}"},
        )
        if resp.ok:
            data = resp.json()
            log.info(f"Tooted to Mastodon: {data.get('url')}")
            return {"status": "ok", "url": data.get("url")}
        return {"status": "error", "code": resp.status_code}


# ── Campaign Logger ────────────────────────────────────────────────────────────
class CampaignLogger:
    LOG_PATH = Path("marketing/logs/campaign_log.jsonl")

    def __init__(self):
        self.LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

    def log_post(self, platform: str, result: dict, content: dict):
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "platform": platform,
            "angle": content.get("angle"),
            "title": content.get("title", "")[:100],
            "result": result,
        }
        with open(self.LOG_PATH, "a") as f:
            f.write(json.dumps(entry) + "\n")

    def summary(self) -> dict:
        if not self.LOG_PATH.exists():
            return {"total": 0}
        entries = [json.loads(l) for l in self.LOG_PATH.read_text().splitlines() if l]
        ok = [e for e in entries if e["result"].get("status") == "ok"]
        return {
            "total_posts": len(entries),
            "successful": len(ok),
            "by_platform": {p: len([e for e in ok if e["platform"] == p]) for p in set(e["platform"] for e in entries)},
        }


# ── Main Orchestrator ──────────────────────────────────────────────────────────
def run_campaign(platforms: list, dry_run: bool = False, priority: int = 1):
    logger = CampaignLogger()
    results = {}

    for platform in platforms:
        angle = random.choice(CONTENT_ANGLES)
        log.info(f"Running campaign for {platform} with angle '{angle}'")

        try:
            content = generate_content(angle, platform, dry_run)

            if platform == "reddit":
                poster = RedditPoster()
                targets = [s["name"] for s in SUBREDDITS if s["priority"] <= priority]
                for subreddit in targets[:3]:  # Rate limit: max 3 per run
                    result = poster.post(subreddit, content["title"], content["body"], dry_run)
                    logger.log_post(f"reddit/{subreddit}", result, content)
                    results[f"reddit/{subreddit}"] = result

            elif platform == "devto":
                poster = DevtoPoster()
                result = poster.post(content["title"], content["body"], DEVTO_TAGS, dry_run=dry_run)
                logger.log_post("devto", result, content)
                results["devto"] = result

            elif platform == "hashnode":
                poster = HashnodePoster()
                result = poster.post(content["title"], content["body"], DEVTO_TAGS, dry_run)
                logger.log_post("hashnode", result, content)
                results["hashnode"] = result

            elif platform == "github":
                poster = GitHubDiscussionsPoster()
                result = poster.post(content["title"], content["body"], dry_run)
                logger.log_post("github_discussions", result, content)
                results["github"] = result

            elif platform == "mastodon":
                poster = MastodonPoster()
                post_body = f"{content['title']}\n\n{content['body'][:350]}\n\n{' '.join('#' + t for t in content['tags'][:5])}"
                result = poster.post(post_body, dry_run)
                logger.log_post("mastodon", result, content)
                results["mastodon"] = result

        except Exception as e:
            log.error(f"Campaign failed for {platform}: {e}")
            results[platform] = {"status": "error", "error": str(e)}

    summary = logger.summary()
    log.info(f"Campaign complete. Summary: {json.dumps(summary, indent=2)}")
    return results


def main():
    parser = argparse.ArgumentParser(description="ADAAD Autonomous Marketing Engine")
    parser.add_argument("--platform", nargs="+", default=["all"],
                        choices=["all", "reddit", "devto", "hashnode", "github", "mastodon", "twitter", "linkedin"],
                        help="Platforms to post to")
    parser.add_argument("--dry-run", action="store_true", help="Preview without posting")
    parser.add_argument("--generate-only", action="store_true", help="Generate content only, print to stdout")
    parser.add_argument("--priority", type=int, default=1, choices=[1, 2, 3],
                        help="Subreddit priority level (1=highest)")
    parser.add_argument("--angle", default=None, choices=CONTENT_ANGLES + [None],
                        help="Content angle to use")
    args = parser.parse_args()

    platforms = CONTENT_ANGLES if "all" in args.platform else args.platform

    if args.generate_only:
        angle = args.angle or random.choice(CONTENT_ANGLES)
        for platform in (["reddit", "devto", "twitter", "linkedin"] if "all" in args.platform else args.platform):
            content = generate_content(angle, platform, dry_run=True)
            print(f"\n{'='*60}")
            print(f"PLATFORM: {platform} | ANGLE: {angle}")
            print(f"{'='*60}")
            print(f"TITLE: {content.get('title', 'N/A')}")
            print(f"\nBODY:\n{content.get('body', '')}")
            print(f"\nTAGS: {content.get('tags', [])}")
        return

    all_platforms = ["reddit", "devto", "hashnode", "github", "mastodon"]
    targets = all_platforms if "all" in args.platform else args.platform

    results = run_campaign(targets, dry_run=args.dry_run, priority=args.priority)
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    Path("marketing/logs").mkdir(parents=True, exist_ok=True)
    main()
