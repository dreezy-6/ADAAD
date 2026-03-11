# SPDX-License-Identifier: MIT
"""Platform Dispatchers — ADAAD Phase 11, M11-02.

One class per platform. Each is a thin, tested HTTP client.
No business logic lives here — just the raw API mechanics.

Platforms:
  GitHubMetaDispatcher   — topics, description, website, social preview note
  GitHubPRDispatcher     — fork → branch → commit → open PR (awesome-* lists)
  GitHubDiscussDispatcher— create/pin GitHub Discussions
  DevToDispatcher        — publish articles via Forem API v1
  RedditDispatcher       — submit link/text posts via Reddit OAuth2
  TwitterDispatcher      — post tweet threads via Twitter API v2
  HumanQueueDispatcher   — writes a draft file + adds to human_queue.json

Author: Dustin L. Reid · InnovativeAI LLC
"""

from __future__ import annotations

import base64
import json
import logging
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

log = logging.getLogger("adaad.marketing.dispatch")


# ─── Low-level HTTP ─────────────────────────────────────────────────────────

def _req(
    url: str,
    method: str = "GET",
    payload: Optional[Dict] = None,
    headers: Optional[Dict] = None,
    timeout: int = 20,
) -> Tuple[int, Any]:
    headers = headers or {}
    data    = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode()
            try:
                return resp.status, json.loads(raw)
            except json.JSONDecodeError:
                return resp.status, raw
    except urllib.error.HTTPError as e:
        try:
            err = json.loads(e.read().decode())
        except Exception:
            err = {"raw": str(e)}
        return e.code, err


# ─── Result ─────────────────────────────────────────────────────────────────

@dataclass
class DispatchResult:
    success:     bool
    live_url:    Optional[str]
    platform_id: Optional[str]
    error:       Optional[str]
    platform:    str


def _ok(platform: str, url: str = "", pid: str = "") -> DispatchResult:
    return DispatchResult(True, url or None, pid or None, None, platform)

def _err(platform: str, msg: str) -> DispatchResult:
    log.error("[%s] %s", platform, msg)
    return DispatchResult(False, None, None, msg, platform)


# ════════════════════════════════════════════════════════════════════════════
# GitHub Meta — topics, description, website
# ════════════════════════════════════════════════════════════════════════════

OPTIMAL_TOPICS = [
    "ai-agents", "autonomous-coding", "code-mutation", "constitutional-ai",
    "governance", "llm", "python", "genetic-algorithm", "android",
    "saas", "devtools", "anthropic", "claude-api", "open-source",
    "ai-safety", "replay", "code-quality", "automation",
    "audit-trail", "deterministic",
]  # 20 topics — GitHub max for discoverability

REPO_DESCRIPTION = (
    "Copilot suggests. Cursor autocompletes. ADAAD governs. "
    "3 AI agents · 16-rule constitutional gate · SHA-256 audit trail. Free, MIT."
)

class GitHubMetaDispatcher:
    API = "https://api.github.com"

    def __init__(self, token: str, owner: str = "dreezy-6", repo: str = "ADAAD"):
        self._token = token
        self._owner = owner
        self._repo  = repo

    def _h(self) -> Dict:
        return {
            "Authorization": f"token {self._token}",
            "Accept": "application/vnd.github.v3+json",
            "Content-Type": "application/json",
        }

    def update_topics(self) -> DispatchResult:
        url = f"{self.API}/repos/{self._owner}/{self._repo}/topics"
        h = {**self._h(), "Accept": "application/vnd.github.mercy-preview+json"}
        status, body = _req(url, "PUT", {"names": OPTIMAL_TOPICS[:20]}, h)
        if status == 200:
            return _ok("github_meta", f"https://github.com/{self._owner}/{self._repo}")
        return _err("github_meta", f"topics HTTP {status}: {body}")

    def update_description(self) -> DispatchResult:
        url = f"{self.API}/repos/{self._owner}/{self._repo}"
        payload = {
            "description":      REPO_DESCRIPTION,
            "homepage":         "https://github.com/InnovativeAI-adaad",
            "has_discussions":  True,
            "has_issues":       True,
        }
        status, body = _req(url, "PATCH", payload, self._h())
        if status == 200:
            return _ok("github_meta", body.get("html_url", ""))
        return _err("github_meta", f"description HTTP {status}: {body}")

    def enable_discussions(self) -> DispatchResult:
        """Ensure GitHub Discussions is enabled (already done via update_description)."""
        return _ok("github_meta", f"https://github.com/{self._owner}/{self._repo}/discussions")


# ════════════════════════════════════════════════════════════════════════════
# GitHub PR — fork + branch + patch + open PR
# ════════════════════════════════════════════════════════════════════════════

class GitHubPRDispatcher:
    API = "https://api.github.com"

    def __init__(self, token: str, fork_owner: str = "dreezy-6"):
        self._token      = token
        self._fork_owner = fork_owner

    def _h(self) -> Dict:
        return {
            "Authorization": f"token {self._token}",
            "Accept": "application/vnd.github.v3+json",
            "Content-Type": "application/json",
        }

    def submit_to_awesome_list(
        self,
        upstream_owner: str,
        upstream_repo:  str,
        file_path:      str,
        addition_line:  str,
        section_marker: str,
        pr_title:       str,
        pr_body:        str,
        target_id:      str,
    ) -> DispatchResult:
        """Full fork → branch → commit → PR for one awesome-list entry."""
        try:
            # 1. Fork
            fork_url = f"{self.API}/repos/{upstream_owner}/{upstream_repo}/forks"
            fs, fb   = _req(fork_url, "POST", {}, self._h())
            if fs not in (200, 202):
                return _err("github_pr", f"fork HTTP {fs}: {fb}")
            time.sleep(3)   # GitHub needs a moment to create the fork

            # 2. Get default branch SHA (try main then master)
            sha, base_branch = None, "main"
            for branch in ("main", "master"):
                ref_url = f"{self.API}/repos/{self._fork_owner}/{upstream_repo}/git/ref/heads/{branch}"
                rs, rb  = _req(ref_url, "GET", None, self._h())
                if rs == 200:
                    sha          = rb["object"]["sha"]
                    base_branch  = branch
                    break
            if not sha:
                return _err("github_pr", "could not get default branch SHA")

            # 3. Create new branch
            branch_name = f"feat/add-adaad-{int(time.time())}"
            br_url      = f"{self.API}/repos/{self._fork_owner}/{upstream_repo}/git/refs"
            bs, _       = _req(br_url, "POST", {"ref": f"refs/heads/{branch_name}", "sha": sha}, self._h())
            if bs not in (200, 201):
                return _err("github_pr", f"branch create HTTP {bs}")

            # 4. Get current file content
            fc_url = f"{self.API}/repos/{self._fork_owner}/{upstream_repo}/contents/{file_path}?ref={branch_name}"
            fcs, fcb = _req(fc_url, "GET", None, self._h())
            if fcs != 200:
                return _err("github_pr", f"get file HTTP {fcs}: {fcb}")

            raw_content = base64.b64decode(fcb["content"].replace("\n", "")).decode("utf-8")
            file_sha    = fcb["sha"]

            # 5. Insert ADAAD line after section_marker (before next ## heading)
            lines   = raw_content.splitlines()
            idx     = len(lines)
            in_sect = False
            for i, line in enumerate(lines):
                if section_marker.lower() in line.lower():
                    in_sect = True
                elif in_sect and line.startswith("## "):
                    idx = i
                    break
            lines.insert(idx, addition_line)
            new_content = "\n".join(lines)

            # 6. Commit
            new_b64   = base64.b64encode(new_content.encode()).decode()
            put_url   = f"{self.API}/repos/{self._fork_owner}/{upstream_repo}/contents/{file_path}"
            cs, cb    = _req(put_url, "PUT", {
                "message": f"feat: add ADAAD — constitutional AI mutation engine",
                "content": new_b64,
                "sha":     file_sha,
                "branch":  branch_name,
            }, self._h())
            if cs not in (200, 201):
                return _err("github_pr", f"commit HTTP {cs}: {cb}")

            # 7. Open PR
            pr_url   = f"{self.API}/repos/{upstream_owner}/{upstream_repo}/pulls"
            prs, prb = _req(pr_url, "POST", {
                "title": pr_title,
                "body":  pr_body,
                "head":  f"{self._fork_owner}:{branch_name}",
                "base":  base_branch,
                "draft": False,
            }, self._h())
            if prs in (200, 201):
                return _ok("github_pr", prb.get("html_url", ""), str(prb.get("number", "")))
            return _err("github_pr", f"PR open HTTP {prs}: {prb}")

        except Exception as exc:
            return _err("github_pr", str(exc))


# ════════════════════════════════════════════════════════════════════════════
# Dev.to
# ════════════════════════════════════════════════════════════════════════════

class DevToDispatcher:
    API = "https://dev.to/api/articles"

    def __init__(self, api_key: str):
        self._key = api_key

    def publish(
        self,
        title: str,
        body_markdown: str,
        tags: list,
        canonical_url: str = "https://github.com/dreezy-6/ADAAD",
        published: bool = True,
    ) -> DispatchResult:
        if not self._key:
            return _err("devto", "DEVTO_API_KEY not set")
        headers = {
            "api-key":     self._key,
            "Content-Type":"application/json",
            "Accept":      "application/vnd.forem.api-v1+json",
        }
        payload = {"article": {
            "title":        title,
            "body_markdown":body_markdown,
            "published":    published,
            "tags":         tags[:4],
            "canonical_url":canonical_url,
        }}
        status, body = _req(self.API, "POST", payload, headers)
        if status in (200, 201):
            return _ok("devto", body.get("url", ""), str(body.get("id", "")))
        return _err("devto", f"HTTP {status}: {body}")


# ════════════════════════════════════════════════════════════════════════════
# Reddit
# ════════════════════════════════════════════════════════════════════════════

class RedditDispatcher:
    TOKEN_URL = "https://www.reddit.com/api/v1/access_token"
    SUBMIT_URL= "https://oauth.reddit.com/api/submit"

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        username: str,
        password: str,
    ):
        self._cid  = client_id
        self._cs   = client_secret
        self._user = username
        self._pass = password
        self._token: Optional[str] = None
        self._token_exp: int = 0

    def _ensure_token(self) -> bool:
        if self._token and time.time() < self._token_exp:
            return True
        if not all([self._cid, self._cs, self._user, self._pass]):
            return False
        creds  = base64.b64encode(f"{self._cid}:{self._cs}".encode()).decode()
        data   = urllib.parse.urlencode({
            "grant_type": "password",
            "username":   self._user,
            "password":   self._pass,
        }).encode()
        req    = urllib.request.Request(
            self.TOKEN_URL, data=data,
            headers={
                "Authorization": f"Basic {creds}",
                "User-Agent":    "ADAAD:v3.5.0 (by /u/InnovativeAI-adaad)",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                body        = json.loads(resp.read().decode())
                self._token = body.get("access_token")
                self._token_exp = int(time.time()) + body.get("expires_in", 3600) - 60
                return bool(self._token)
        except Exception as exc:
            log.error("Reddit auth error: %s", exc)
            return False

    def submit_link(self, subreddit: str, title: str, url: str) -> DispatchResult:
        return self._submit(subreddit, title, "link", url=url)

    def submit_text(self, subreddit: str, title: str, text: str) -> DispatchResult:
        return self._submit(subreddit, title, "self", text=text)

    def _submit(
        self, subreddit: str, title: str, kind: str,
        url: str = "", text: str = "",
    ) -> DispatchResult:
        if not self._ensure_token():
            return _err("reddit", "Reddit OAuth credentials not configured or auth failed")
        payload = {
            "sr":    subreddit,
            "title": title,
            "kind":  kind,
            "resubmit": False,
            "sendreplies": True,
        }
        if kind == "link":
            payload["url"]  = url
        else:
            payload["text"] = text

        data    = urllib.parse.urlencode(payload).encode()
        headers = {
            "Authorization": f"bearer {self._token}",
            "User-Agent":    "ADAAD:v3.5.0 (by /u/InnovativeAI-adaad)",
            "Content-Type":  "application/x-www-form-urlencoded",
        }
        req  = urllib.request.Request(self.SUBMIT_URL, data=data, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                body    = json.loads(resp.read().decode())
                post_url= body.get("jquery", [[]])[10][3][0] if "jquery" in body else ""
                if body.get("success") or post_url:
                    return _ok("reddit", post_url)
                return _err("reddit", f"Reddit rejected: {body}")
        except Exception as exc:
            return _err("reddit", str(exc))


# ════════════════════════════════════════════════════════════════════════════
# Twitter / X — v2 API
# ════════════════════════════════════════════════════════════════════════════

class TwitterDispatcher:
    API = "https://api.twitter.com/2/tweets"

    def __init__(self, bearer_token: str):
        self._token = bearer_token

    def post_tweet(self, text: str) -> DispatchResult:
        if not self._token:
            return _err("twitter", "TWITTER_BEARER_TOKEN not set")
        headers = {
            "Authorization": f"Bearer {self._token}",
            "Content-Type":  "application/json",
        }
        status, body = _req(self.API, "POST", {"text": text[:280]}, headers)
        if status in (200, 201):
            tid = body.get("data", {}).get("id", "")
            return _ok("twitter", f"https://twitter.com/i/web/status/{tid}", tid)
        return _err("twitter", f"HTTP {status}: {body}")

    def post_thread(self, tweets: list) -> DispatchResult:
        """Post a thread (each tweet replies to the previous)."""
        if not self._token:
            return _err("twitter", "TWITTER_BEARER_TOKEN not set")
        prev_id   = None
        first_url = None
        for text in tweets:
            payload = {"text": text[:280]}
            if prev_id:
                payload["reply"] = {"in_reply_to_tweet_id": prev_id}
            status, body = _req(
                self.API, "POST", payload,
                {
                    "Authorization": f"Bearer {self._token}",
                    "Content-Type": "application/json",
                }
            )
            if status not in (200, 201):
                return _err("twitter", f"Thread tweet HTTP {status}: {body}")
            prev_id = body.get("data", {}).get("id", "")
            if not first_url:
                first_url = f"https://twitter.com/i/web/status/{prev_id}"
            time.sleep(1)   # avoid burst rate limit
        return _ok("twitter", first_url or "", prev_id or "")


# ════════════════════════════════════════════════════════════════════════════
# Human Queue — writes draft files for actions needing Dustin
# ════════════════════════════════════════════════════════════════════════════

class HumanQueueDispatcher:
    """Writes drafted content to marketing/human_queue/ for manual posting."""

    def __init__(self, queue_dir: str = "marketing/human_queue"):
        self._dir = Path(queue_dir)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._index_file = self._dir / "queue.json"
        self._index: list = self._load_index()

    def _load_index(self) -> list:
        if self._index_file.exists():
            return json.loads(self._index_file.read_text())
        return []

    def _save_index(self) -> None:
        self._index_file.write_text(json.dumps(self._index, indent=2))

    def enqueue(
        self,
        target_id: str,
        platform:  str,
        title:     str,
        action:    str,
        why:       str,
        draft_content: str,
        draft_filename: str,
    ) -> DispatchResult:
        # Write draft file
        draft_path = self._dir / draft_filename
        draft_path.write_text(draft_content)

        # Add to index
        item = {
            "target_id":    target_id,
            "platform":     platform,
            "title":        title,
            "action":       action,
            "why":          why,
            "draft_file":   str(draft_path),
            "queued_at":    int(time.time()),
            "completed":    False,
        }
        # Avoid duplicates
        self._index = [i for i in self._index if i["target_id"] != target_id]
        self._index.append(item)
        self._save_index()

        log.info("[human_queue] Enqueued: %s → %s", target_id, draft_path)
        return _ok("human_queue", str(draft_path))

    def all_pending(self) -> list:
        return [i for i in self._index if not i.get("completed")]

    def mark_complete(self, target_id: str) -> None:
        for item in self._index:
            if item["target_id"] == target_id:
                item["completed"] = True
        self._save_index()


# ════════════════════════════════════════════════════════════════════════════
# Mastodon Dispatcher — fosstodon.org (FOSS dev community, free API)
# ════════════════════════════════════════════════════════════════════════════

MASTODON_HASHTAGS = "#OpenSource #AI #DevTools #Python #ConstitutionalAI #FOSS #AuditTrail"

MASTODON_POSTS = [
    {
        "id":    "mastodon-launch",
        "angle": "launch",
        "text":  (
            "Just open-sourced ADAAD — constitutional AI governance for autonomous code mutation.\n\n"
            "3 Claude agents compete → genetic algorithm ranks → 16-rule governance gate "
            "approves or halts → SHA-256 hash-chained audit trail.\n\n"
            "Nothing ships without cryptographic proof. Free forever. MIT.\n\n"
            "https://github.com/InnovativeAI-adaad/ADAAD\n\n"
            "#OpenSource #AI #DevTools #Python #FOSS"
        ),
    },
    {
        "id":    "mastodon-audit-trail",
        "angle": "audit_trail",
        "text":  (
            "The question every AI coding tool should answer but can't:\n\n"
            "\"What exactly changed, when, under what conditions, and can you prove it?\"\n\n"
            "ADAAD answers this with a SHA-256 hash-chained evidence ledger and "
            "deterministic replay — re-run any past epoch, get byte-identical outputs.\n\n"
            "https://github.com/InnovativeAI-adaad/ADAAD\n\n"
            "#AI #AuditTrail #OpenSource #ConstitutionalAI"
        ),
    },
    {
        "id":    "mastodon-vs-copilot",
        "angle": "comparison",
        "text":  (
            "Copilot suggests. Cursor autocompletes.\n\n"
            "ADAAD governs — with 3 competing agents, a genetic algorithm, "
            "a 16-rule constitutional gate, and a cryptographic audit trail.\n\n"
            "The governance gate cannot be overridden. Architectural invariant, "
            "not a config flag. Free, MIT, self-hosted.\n\n"
            "pip install adaad\n"
            "https://github.com/InnovativeAI-adaad/ADAAD\n\n"
            "#DevTools #AI #FOSS #OpenSource"
        ),
    },
    {
        "id":    "mastodon-android",
        "angle": "android",
        "text":  (
            "Monitor your AI code mutations from your phone.\n\n"
            "ADAAD has a free Android companion app — watch epochs run, "
            "review governance decisions, and inspect the audit trail "
            "from anywhere.\n\n"
            "The whole system is free forever. MIT licensed. Self-hosted.\n\n"
            "https://github.com/InnovativeAI-adaad/ADAAD\n\n"
            "#Android #FOSS #AI #OpenSource"
        ),
    },
    {
        "id":    "mastodon-free-forever",
        "angle": "free",
        "text":  (
            "ADAAD Community tier:\n"
            "✓ Full constitutional governance engine\n"
            "✓ SHA-256 evidence ledger\n"
            "✓ Deterministic replay\n"
            "✓ Android companion app\n"
            "✓ No telemetry\n"
            "✓ Self-hosted\n"
            "✓ MIT licensed\n"
            "✓ Free forever\n\n"
            "pip install adaad\n"
            "https://github.com/InnovativeAI-adaad/ADAAD\n\n"
            "#OpenSource #FOSS #AI #FreeSoftware"
        ),
    },
]


class MastodonDispatcher:
    """Post status updates to a Mastodon instance (fosstodon.org by default).

    Requires:
      MASTODON_ACCESS_TOKEN — from instance settings → Applications → New Application
      MASTODON_INSTANCE     — e.g. fosstodon.org (default)

    API docs: https://docs.joinmastodon.org/client/intro/
    """

    def __init__(self, access_token: str, instance: str = "fosstodon.org"):
        self._token    = access_token
        self._instance = instance.rstrip("/")
        self._api_base = f"https://{self._instance}/api/v1"

    def post(self, text: str) -> "DispatchResult":
        if not self._token:
            return _err("mastodon", "MASTODON_ACCESS_TOKEN not set")

        # Mastodon character limit: 500 on most instances
        if len(text) > 500:
            text = text[:497] + "…"

        status_url = f"{self._api_base}/statuses"
        payload    = json.dumps({"status": text, "visibility": "public"}).encode()
        req = urllib.request.Request(
            status_url,
            data=payload,
            headers={
                "Authorization":  f"Bearer {self._token}",
                "Content-Type":   "application/json",
                "User-Agent":     "ADAAD-MarketingBot/6.2 (https://github.com/InnovativeAI-adaad/ADAAD)",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                data    = json.loads(resp.read().decode())
                post_url = data.get("url", "")
                pid      = data.get("id", "")
                log.info("[mastodon] Posted: %s", post_url)
                return _ok("mastodon", post_url, pid)
        except urllib.error.HTTPError as e:
            raw = e.read().decode()
            return _err("mastodon", f"HTTP {e.code}: {raw[:200]}")
        except Exception as exc:
            return _err("mastodon", str(exc))


# ════════════════════════════════════════════════════════════════════════════
# GitHub Discussions Dispatcher — SEO + developer community
# ════════════════════════════════════════════════════════════════════════════

DISCUSSION_SEEDS = [
    {
        "id":       "discussion-intro",
        "title":    "Welcome to ADAAD — constitutional AI governance for your codebase",
        "body":     (
            "## What is ADAAD?\n\n"
            "ADAAD is an open-source AI coding governance system. Three Claude-powered agents "
            "(Architect, Dream, Beast) compete continuously to improve your codebase. Every "
            "proposal passes a 16-rule constitutional governance gate before a single byte changes.\n\n"
            "The outcome: **cryptographically auditable, deterministically replayable code mutations** "
            "— SHA-256 hash-chained into an immutable evidence ledger.\n\n"
            "## Why this matters\n\n"
            "When your AI coding tool breaks production, can you answer:\n"
            "- *What exactly changed?*\n"
            "- *Under what conditions?*\n"
            "- *With what evidence?*\n\n"
            "Copilot and Cursor can't answer these questions. ADAAD is designed from the ground up "
            "to answer them — with cryptographic proof.\n\n"
            "## Get started\n\n"
            "```bash\npip install adaad && adaad --dry-run\n```\n\n"
            "Or clone: https://github.com/InnovativeAI-adaad/ADAAD\n\n"
            "---\n"
            "*Built by Dustin L. Reid · InnovativeAI LLC · Blackwell, Oklahoma*\n\n"
            "Questions, ideas, or feedback? This is the right place."
        ),
    },
    {
        "id":       "discussion-faq",
        "title":    "FAQ: Common questions about the Constitutional Gate and audit trail",
        "body":     (
            "## Frequently Asked Questions\n\n"
            "**Q: Can the 16-rule constitutional gate be disabled?**\n"
            "A: No. The GovernanceGate is an architectural invariant — it cannot be overridden "
            "by any agent, operator, configuration flag, or pricing tier. This is not a policy. "
            "It is baked into the code.\n\n"
            "**Q: What is deterministic replay?**\n"
            "A: Every epoch is computed from deterministic inputs (no system time, seeded RNG "
            "anchored to epoch_id). Six months from now, you can re-run any past epoch from "
            "its original inputs and get byte-identical outputs. If they diverge, the pipeline halts.\n\n"
            "**Q: Is the SHA-256 ledger actually immutable?**\n"
            "A: Each entry contains a SHA-256 hash of the previous entry. Modifying any past "
            "entry breaks the hash chain. The system detects this and halts on any divergence.\n\n"
            "**Q: How is ADAAD different from GitHub Copilot?**\n"
            "A: Copilot is autocomplete. ADAAD is autonomous governed mutation with "
            "cryptographic accountability. Copilot cannot add a constitutional gate without "
            "rebuilding its architecture from scratch.\n\n"
            "**Q: What does the free tier include?**\n"
            "A: The full governance engine — all 16 rules, SHA-256 ledger, deterministic replay, "
            "and Android companion app. 50 epochs/month, 3 candidates/epoch. MIT, self-hosted, no telemetry.\n\n"
            "---\n\nPost your question below — Dustin responds to all of them."
        ),
    },
    {
        "id":       "discussion-show-and-tell",
        "title":    "Show and tell: what are you using ADAAD to govern?",
        "body":     (
            "This thread is for sharing what you're using ADAAD on.\n\n"
            "- What kind of codebase?\n"
            "- Which agents are producing the most useful proposals?\n"
            "- Has the constitutional gate caught anything you wouldn't have noticed?\n\n"
            "Every use case helps shape the roadmap — which is itself governed by ADAAD.\n\n"
            "Drop your setup below.\n\n"
            "---\n*If you're new: pip install adaad && adaad --dry-run to start in 60 seconds.*"
        ),
    },
]


class GitHubDiscussDispatcher:
    """Create and pin discussions in the ADAAD GitHub repository.

    Uses the GitHub GraphQL API to create Discussions in a specified category.
    Discussions are indexed by Google and surface in GitHub search — free SEO.

    Requires:
      GITHUB_TOKEN — standard GitHub Actions token works (discussions: write permission)
    """

    GQL_URL = "https://api.github.com/graphql"

    def __init__(self, token: str, owner: str = "InnovativeAI-adaad", repo: str = "ADAAD"):
        self._token = token
        self._owner = owner
        self._repo  = repo

    def _gql(self, query: str, variables: dict) -> dict:
        payload = json.dumps({"query": query, "variables": variables}).encode()
        req = urllib.request.Request(
            self.GQL_URL,
            data=payload,
            headers={
                "Authorization": f"Bearer {self._token}",
                "Content-Type":  "application/json",
                "User-Agent":    "ADAAD-MarketingBot/6.2",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read().decode())

    def _get_repo_id_and_category(self) -> tuple:
        """Return (repo_id, category_id) for the General or Announcements category."""
        data = self._gql(
            """query($owner:String!,$name:String!){
               repository(owner:$owner,name:$name){
                 id
                 discussionCategories(first:10){
                   nodes{id name}
                 }
               }
            }""",
            {"owner": self._owner, "name": self._repo},
        )
        repo = data.get("data", {}).get("repository", {})
        repo_id = repo.get("id")
        cats = repo.get("discussionCategories", {}).get("nodes", [])
        cat_id = None
        for cat in cats:
            if cat["name"].lower() in ("general", "announcements", "q&a", "show and tell"):
                cat_id = cat["id"]
                break
        if not cat_id and cats:
            cat_id = cats[0]["id"]
        return repo_id, cat_id

    def create(self, title: str, body: str) -> "DispatchResult":
        if not self._token:
            return _err("github_discuss", "GITHUB_TOKEN not set")
        try:
            repo_id, cat_id = self._get_repo_id_and_category()
            if not repo_id or not cat_id:
                return _err("github_discuss", "Could not resolve repo/category IDs")
            data = self._gql(
                """mutation($input:CreateDiscussionInput!){
                   createDiscussion(input:$input){
                     discussion{url id}
                   }
                }""",
                {"input": {"repositoryId": repo_id, "categoryId": cat_id,
                           "title": title, "body": body}},
            )
            disc = data.get("data", {}).get("createDiscussion", {}).get("discussion", {})
            url  = disc.get("url", "")
            pid  = disc.get("id", "")
            if url:
                log.info("[github_discuss] Created: %s", url)
                return _ok("github_discuss", url, pid)
            errors = data.get("errors", [])
            return _err("github_discuss", str(errors))
        except Exception as exc:
            return _err("github_discuss", str(exc))
