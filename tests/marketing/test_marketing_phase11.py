# SPDX-License-Identifier: MIT
"""Tests — ADAAD Phase 11 Autonomous Marketing Engine.

T11-01  MarketingStateStore — logs action to JSONL
T11-02  MarketingStateStore — elapsed_since returns inf for new target
T11-03  MarketingStateStore — elapsed_since calculates correctly
T11-04  MarketingStateStore — coverage_report correct counts
T11-05  MarketingGate — blocks when interval not elapsed
T11-06  MarketingGate — passes when interval elapsed
T11-07  GitHubMetaDispatcher — OPTIMAL_TOPICS has ≥ 10 entries, all strings
T11-08  GitHubMetaDispatcher — REPO_DESCRIPTION < 350 chars
T11-09  GitHubPRDispatcher — addition_line contains repo URL
T11-10  DevToDispatcher — returns error result when no API key
T11-11  RedditDispatcher — returns error result when no credentials
T11-12  TwitterDispatcher — returns error result when no token
T11-13  HumanQueueDispatcher — enqueue writes file and updates index
T11-14  HumanQueueDispatcher — enqueue is idempotent (no duplicates)
T11-15  AWESOME_LIST_TARGETS — all required fields present
T11-16  DEVTO_ARTICLES — all required fields present
T11-17  REDDIT_TARGETS — all min_interval_h are ≥ 720 (no spam)
T11-18  HUMAN_QUEUE_TARGETS — all 3 key manual targets are registered
T11-19  market.py — file exists and is executable
T11-20  EngineConfig — dry_run default is False
T11-21  AutonomousMarketingEngine — run() dry_run returns zero failures
T11-22  AutonomousMarketingEngine — status_report returns expected keys
T11-23  CITATION.cff — exists and contains required fields
T11-24  PRESS.md — exists and contains pitch boilerplate
T11-25  autonomous_marketing.yml — cron schedule present
T11-26  autonomous_marketing.yml — workflow_dispatch with dry_run input

Author: Dustin L. Reid · InnovativeAI LLC
"""

import json
import os
import pathlib
import tempfile
import time

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]


# ─── State store ─────────────────────────────────────────────────────────────

def test_t1101_state_store_logs_action(tmp_path):
    from runtime.marketing.state import MarketingStateStore, MarketingAction
    store = MarketingStateStore(str(tmp_path / "state"))
    action = MarketingAction(
        action_id="test-001", target_id="devto-intro", platform="devto",
        content_type="article", title="Test Article", success=True,
        live_url="https://dev.to/test", error=None,
        dispatched_at=int(time.time()), dry_run=False,
    )
    store.log_action(action)
    recent = store.recent_actions(5)
    assert len(recent) == 1
    assert recent[0].target_id == "devto-intro"
    assert recent[0].success is True


def test_t1102_elapsed_inf_for_new_target(tmp_path):
    from runtime.marketing.state import MarketingStateStore
    store = MarketingStateStore(str(tmp_path / "state"))
    assert store.elapsed_since_last_action("unknown-target") == float("inf")


def test_t1103_elapsed_calculates_correctly(tmp_path):
    from runtime.marketing.state import MarketingStateStore, TargetState
    store = MarketingStateStore(str(tmp_path / "state"))
    state = TargetState("reddit-python", "reddit")
    state.last_action_at = int(time.time()) - 3600   # 1 hour ago
    store.upsert_target(state)
    elapsed = store.elapsed_since_last_action("reddit-python")
    assert 0.9 < elapsed < 1.1


def test_t1104_coverage_report(tmp_path):
    from runtime.marketing.state import MarketingStateStore, TargetState
    store = MarketingStateStore(str(tmp_path / "state"))
    t1 = TargetState("devto-intro",   "devto");   t1.status = "live";    t1.live_url = "https://dev.to/x"
    t2 = TargetState("reddit-python", "reddit");  t2.status = "pending"
    store.upsert_target(t1)
    store.upsert_target(t2)
    rep = store.coverage_report(total_known_targets=2)
    assert rep["live"]         == 1
    assert rep["pending"]      == 1
    assert rep["coverage_pct"] == 50.0


# ─── Marketing gate ───────────────────────────────────────────────────────────

def test_t1105_gate_blocks_when_interval_not_elapsed(tmp_path):
    from runtime.marketing.state import MarketingStateStore, TargetState
    from runtime.marketing.engine import MarketingGate
    store = MarketingStateStore(str(tmp_path / "state"))
    state = TargetState("devto-intro", "devto")
    state.last_action_at = int(time.time()) - 600   # 10 min ago
    store.upsert_target(state)
    gate  = MarketingGate(store)
    ok, reason = gate.check("devto-intro", min_interval_h=24)
    assert ok is False
    assert "rate-limited" in reason


def test_t1106_gate_passes_when_interval_elapsed(tmp_path):
    from runtime.marketing.state import MarketingStateStore
    from runtime.marketing.engine import MarketingGate
    store = MarketingStateStore(str(tmp_path / "state"))
    gate  = MarketingGate(store)
    ok, reason = gate.check("brand-new-target", min_interval_h=168)
    assert ok is True
    assert reason == "ok"


# ─── GitHub meta ─────────────────────────────────────────────────────────────

def test_t1107_optimal_topics_count():
    from runtime.marketing.dispatchers import OPTIMAL_TOPICS
    assert len(OPTIMAL_TOPICS) >= 10
    assert all(isinstance(t, str) for t in OPTIMAL_TOPICS)
    assert all(t == t.lower() for t in OPTIMAL_TOPICS)   # GitHub topics are lowercase


def test_t1108_repo_description_length():
    from runtime.marketing.dispatchers import REPO_DESCRIPTION
    assert len(REPO_DESCRIPTION) <= 350
    assert len(REPO_DESCRIPTION) >= 50


# ─── Awesome-list PR config ───────────────────────────────────────────────────

def test_t1109_pr_targets_have_repo_url():
    from runtime.marketing.engine import AWESOME_LIST_TARGETS, REPO_URL
    for t in AWESOME_LIST_TARGETS:
        assert REPO_URL in t["addition_line"], (
            f"{t['target_id']} addition_line missing repo URL"
        )


# ─── Dispatchers — error paths ────────────────────────────────────────────────

def test_t1110_devto_no_key():
    from runtime.marketing.dispatchers import DevToDispatcher
    d = DevToDispatcher(api_key="")
    r = d.publish("Test", "body", [])
    assert r.success is False
    assert "DEVTO_API_KEY" in (r.error or "")


def test_t1111_reddit_no_creds():
    from runtime.marketing.dispatchers import RedditDispatcher
    d = RedditDispatcher("", "", "", "")
    r = d.submit_link("Python", "Test", "https://example.com")
    assert r.success is False


def test_t1112_twitter_no_token():
    from runtime.marketing.dispatchers import TwitterDispatcher
    d = TwitterDispatcher("")
    r = d.post_tweet("Hello")
    assert r.success is False
    assert "TWITTER_BEARER_TOKEN" in (r.error or "")


# ─── Human queue ─────────────────────────────────────────────────────────────

def test_t1113_human_queue_enqueue(tmp_path):
    from runtime.marketing.dispatchers import HumanQueueDispatcher
    q = HumanQueueDispatcher(str(tmp_path / "hq"))
    q.enqueue(
        target_id="hn-test", platform="HN", title="Test",
        action="Submit", why="High ROI",
        draft_content="# Draft\n\nhello", draft_filename="test_draft.md",
    )
    assert (tmp_path / "hq" / "test_draft.md").exists()
    assert len(q.all_pending()) == 1
    assert q.all_pending()[0]["target_id"] == "hn-test"


def test_t1114_human_queue_idempotent(tmp_path):
    from runtime.marketing.dispatchers import HumanQueueDispatcher
    q = HumanQueueDispatcher(str(tmp_path / "hq"))
    for _ in range(3):
        q.enqueue(
            target_id="hn-test", platform="HN", title="Test",
            action="Submit", why="Why",
            draft_content="body", draft_filename="test.md",
        )
    assert len(q.all_pending()) == 1   # deduplicated


# ─── Content registry completeness ───────────────────────────────────────────

def test_t1115_awesome_list_targets_have_required_fields():
    from runtime.marketing.engine import AWESOME_LIST_TARGETS
    required = {"target_id", "upstream_owner", "upstream_repo", "file_path",
                "section_marker", "addition_line", "pr_title", "pr_body",
                "platform", "min_interval_h"}
    for t in AWESOME_LIST_TARGETS:
        missing = required - set(t.keys())
        assert not missing, f"{t.get('target_id')} missing: {missing}"


def test_t1116_devto_articles_have_required_fields():
    from runtime.marketing.engine import DEVTO_ARTICLES
    for a in DEVTO_ARTICLES:
        assert "target_id" in a
        assert "title" in a
        assert "tags" in a
        assert len(a["tags"]) >= 1


def test_t1117_reddit_targets_no_spam():
    from runtime.marketing.engine import REDDIT_TARGETS
    for t in REDDIT_TARGETS:
        assert t["min_interval_h"] >= 720, (
            f"{t['target_id']} has min_interval_h={t['min_interval_h']} — must be ≥ 720 (30 days)"
        )


def test_t1118_human_queue_targets_registered():
    from runtime.marketing.engine import HUMAN_QUEUE_TARGETS
    ids = {t["target_id"] for t in HUMAN_QUEUE_TARGETS}
    assert "hackernews-show-hn"  in ids
    assert "producthunt-launch"  in ids
    assert "indiehackers-post"   in ids


# ─── Entry point ─────────────────────────────────────────────────────────────

def test_t1119_market_py_exists():
    assert (ROOT / "market.py").exists()
    content = (ROOT / "market.py").read_text()
    assert "AutonomousMarketingEngine" in content
    assert "--dry-run" in content
    assert "--discover" in content


def test_t1120_engine_config_dry_run_default():
    from runtime.marketing.engine import EngineConfig
    cfg = EngineConfig()
    assert cfg.dry_run is False


def test_t1121_engine_dry_run_no_failures(tmp_path):
    from runtime.marketing.engine import AutonomousMarketingEngine, EngineConfig
    cfg = EngineConfig(
        dry_run=True,
        state_dir=str(tmp_path / "state"),
        drafts_dir=str(tmp_path / "drafts"),
        human_queue_dir=str(tmp_path / "hq"),
    )
    engine  = AutonomousMarketingEngine(cfg)
    results = engine.run(target_filter="all")
    # Dry run: everything should be skipped, never failed
    assert results["failed"] == 0


def test_t1122_status_report_keys(tmp_path):
    from runtime.marketing.engine import AutonomousMarketingEngine, EngineConfig
    cfg = EngineConfig(
        dry_run=True,
        state_dir=str(tmp_path / "state"),
        drafts_dir=str(tmp_path / "drafts"),
        human_queue_dir=str(tmp_path / "hq"),
    )
    engine = AutonomousMarketingEngine(cfg)
    report = engine.status_report()
    assert "coverage"       in report
    assert "recent_actions" in report
    assert "human_queue"    in report


# ─── Static files ────────────────────────────────────────────────────────────

def test_t1123_citation_cff_exists():
    p = ROOT / "CITATION.cff"
    assert p.exists(), "CITATION.cff is required for Google Scholar indexing"
    content = p.read_text()
    assert "Dustin"      in content
    assert "InnovativeAI" in content
    assert "dreezy-6/ADAAD" in content
    assert "cff-version"  in content


def test_t1124_press_md_exists():
    p = ROOT / "PRESS.md"
    assert p.exists(), "PRESS.md press kit is required"
    content = p.read_text()
    assert "dreezy-6/ADAAD" in content
    assert "Dustin" in content
    assert "boilerplate" in content.lower() or "Boilerplate" in content


def test_t1125_marketing_workflow_has_cron():
    wf = ROOT / ".github" / "workflows" / "autonomous_marketing.yml"
    assert wf.exists()
    content = wf.read_text()
    assert "cron:" in content
    assert "schedule:" in content
    assert "0 9 * * *" in content   # daily 9am UTC


def test_t1126_marketing_workflow_has_dry_run_input():
    wf = ROOT / ".github" / "workflows" / "autonomous_marketing.yml"
    content = wf.read_text()
    assert "workflow_dispatch" in content
    assert "dry_run" in content
    assert "discover" in content
