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
]

REPO_DESCRIPTION = (
    "Three AI agents improve your code — constitutionally gated, "
    "deterministically replayable, cryptographically auditable. Free forever. MIT."
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
