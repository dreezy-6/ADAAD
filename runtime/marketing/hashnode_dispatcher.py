# SPDX-License-Identifier: MIT
"""HashnodeDispatcher — ADAAD Phase 12 Campaign Blitz v2.

Hashnode is a free developer blogging platform with 1M+ monthly readers.
Articles posted here surface on hashnode.com/feed and can optionally be
published to your own custom domain (e.g. blog.innovativeai.llc).

API docs: https://apidocs.hashnode.com/

Author: Dustin L. Reid · InnovativeAI LLC
"""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

log = logging.getLogger("adaad.marketing.hashnode")

HASHNODE_GQL_URL = "https://gql.hashnode.com"


def _gql(query: str, variables: Dict, token: str, timeout: int = 20) -> Tuple[int, Any]:
    payload = json.dumps({"query": query, "variables": variables}).encode()
    req = urllib.request.Request(
        HASHNODE_GQL_URL,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": token,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode()
            return resp.status, json.loads(raw)
    except urllib.error.HTTPError as e:
        try:
            err = json.loads(e.read().decode())
        except Exception:
            err = {"raw": str(e)}
        return e.code, err


# GraphQL mutation to publish a post on Hashnode
PUBLISH_POST_MUTATION = """
mutation PublishPost($input: PublishPostInput!) {
  publishPost(input: $input) {
    post {
      id
      url
      slug
    }
  }
}
"""

# The 3 canonical ADAAD Hashnode articles
HASHNODE_ARTICLES = [
    {
        "target_id": "hashnode-intro",
        "title": "ADAAD: Constitutional AI governance for autonomous code mutation",
        "subtitle": "Three AI agents improve your code. A 16-rule constitution approves every byte. Nothing ships without proof.",
        "tags": ["ai", "python", "opensource", "devtools", "governance"],
        "body_key": "hashnode_intro",
        "canonical_url": "https://github.com/InnovativeAI-adaad/ADAAD",
        "min_interval_h": 0,  # one-shot
    },
    {
        "target_id": "hashnode-governance",
        "title": "How ADAAD's 16-rule constitutional gate stops autonomous AI from going wrong",
        "subtitle": "A deep dive into fail-closed governance, deterministic replay, and cryptographic audit trails.",
        "tags": ["aisafety", "ai", "security", "opensource", "python"],
        "body_key": "hashnode_governance",
        "canonical_url": "https://github.com/InnovativeAI-adaad/ADAAD/blob/main/docs/CONSTITUTION.md",
        "min_interval_h": 0,
    },
    {
        "target_id": "hashnode-saas",
        "title": "From MIT open-source to SaaS: how InnovativeAI monetized a governed AI devtool",
        "subtitle": "Community free forever. Pro at $49/mo. Enterprise at $499/mo. The constitution keeps every tier equal.",
        "tags": ["saas", "indiehacker", "ai", "startup", "opensource"],
        "body_key": "hashnode_saas",
        "canonical_url": "https://github.com/InnovativeAI-adaad/ADAAD/blob/main/PRICING.md",
        "min_interval_h": 0,
    },
]


@dataclass
class HashnodeResult:
    success: bool
    live_url: Optional[str]
    post_id: Optional[str]
    error: Optional[str]


class HashnodeDispatcher:
    """Publish articles to Hashnode via GraphQL API.

    Requires:
        HASHNODE_TOKEN       — Hashnode Personal Access Token
        HASHNODE_PUBLICATION_ID — Publication (blog) ID from Hashnode dashboard
    """

    PLATFORM = "hashnode"

    def __init__(self, token: str, publication_id: str) -> None:
        self._token = token
        self._pub_id = publication_id

    def publish(
        self,
        title: str,
        subtitle: str,
        content_markdown: str,
        tags: list[str],
        canonical_url: Optional[str] = None,
    ) -> HashnodeResult:
        if not self._token or not self._pub_id:
            return HashnodeResult(False, None, None, "HASHNODE_TOKEN or HASHNODE_PUBLICATION_ID not set")

        tag_objs = [{"slug": t.lower().replace(" ", "-"), "name": t} for t in tags]

        variables = {
            "input": {
                "title": title,
                "subtitle": subtitle,
                "publicationId": self._pub_id,
                "contentMarkdown": content_markdown,
                "tags": tag_objs,
                "originalArticleURL": canonical_url or "",
                "disableComments": False,
            }
        }

        status, body = _gql(PUBLISH_POST_MUTATION, variables, self._token)
        if status != 200 or "errors" in body:
            err = body.get("errors", [{}])[0].get("message", str(body))
            log.error("[hashnode] publish failed: %s", err)
            return HashnodeResult(False, None, None, err)

        post = body.get("data", {}).get("publishPost", {}).get("post", {})
        url = post.get("url", "")
        pid = post.get("id", "")
        log.info("[hashnode] published: %s", url)
        return HashnodeResult(True, url, pid, None)
