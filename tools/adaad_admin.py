#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""ADAAD Admin CLI — InnovativeAI LLC Operations Tool.

Command-line interface for Dustin L. Reid to manage ADAAD customer
organisations, API keys, revenue, and governance health.

Usage:
    python tools/adaad_admin.py <command> [options]

Commands:
    org create  --org-id <slug> --name <name> --tier <tier>
    org list    [--tier <tier>] [--status <status>]
    org tier    --org-id <slug> --tier <tier>
    org delete  --org-id <slug>

    key generate  --org-id <slug> --tier <tier>
    key rotate    --org-id <slug>
    key verify    --token <key>

    revenue  [--epoch-window <YYYY-MM>]
    usage    --org-id <slug> [--epoch-window <YYYY-MM>]

    health   (system health + gate status)

Author: Dustin L. Reid · InnovativeAI LLC · Blackwell, Oklahoma
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional

# ---------------------------------------------------------------------------
# Bootstrap path
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def _require_env(var: str) -> str:
    val = os.environ.get(var, "")
    if not val:
        print(f"ERROR: {var} is not set. Export it before running the admin CLI.", file=sys.stderr)
        sys.exit(1)
    return val


def _json_out(data: Any) -> None:
    print(json.dumps(data, indent=2, default=str))


# ---------------------------------------------------------------------------
# Lazy service initialisation
# ---------------------------------------------------------------------------

def _build_services():
    from runtime.monetization.api_key_manager import ApiKeyManager
    from runtime.monetization.org_registry import OrgRegistry
    from runtime.monetization.onboarding_service import OnboardingService
    from runtime.monetization.usage_tracker import UsageTracker
    from runtime.monetization.tier_engine import TierEngine, Tier, ALL_TIERS

    signing_key = _require_env(ApiKeyManager.ENV_SIGNING_KEY)
    km  = ApiKeyManager(signing_key=signing_key.encode())
    reg = OrgRegistry()
    ob  = OnboardingService(reg, km)
    ut  = UsageTracker()
    te  = TierEngine()
    return km, reg, ob, ut, te


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_org_create(args) -> None:
    km, reg, ob, ut, te = _build_services()
    expires_at: Optional[int] = None
    if args.expires_days:
        expires_at = int(time.time()) + args.expires_days * 86_400

    try:
        result = ob.onboard(
            org_id       = args.org_id,
            display_name = args.name or args.org_id,
            tier         = args.tier,
            expires_at   = expires_at,
        )
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

    print(f"\n✅  Organisation '{args.org_id}' created ({args.tier} tier)")
    print(f"\n{'=' * 60}")
    print(f"  API KEY (store securely — shown once):")
    print(f"\n  {result.api_key}\n")
    print(f"  Key ID:  {result.kid}")
    print(f"  Org ID:  {result.org.org_id}")
    print(f"  Tier:    {result.tier}")
    print(f"{'=' * 60}\n")
    print("Next: Set ADAAD_API_KEY=<key> in the customer's environment.")


def cmd_org_list(args) -> None:
    _, reg, *_ = _build_services()
    orgs = reg.list_all()
    if args.tier:
        orgs = [o for o in orgs if o.tier == args.tier]
    if args.status:
        orgs = [o for o in orgs if o.status.value == args.status]

    if not orgs:
        print("No organisations found.")
        return

    print(f"\n{'ORG ID':<30} {'TIER':<14} {'STATUS':<14} {'CREATED'}")
    print("-" * 80)
    for org in sorted(orgs, key=lambda o: o.created_at):
        created = time.strftime("%Y-%m-%d", time.gmtime(org.created_at))
        print(f"{org.org_id:<30} {org.tier:<14} {org.status.value:<14} {created}")
    print(f"\nTotal: {len(orgs)} org(s)")


def cmd_org_tier(args) -> None:
    _, reg, *_ = _build_services()
    try:
        org = reg.set_tier(args.org_id, args.tier, reason=args.reason or "admin-cli")
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
    print(f"✅  {args.org_id} tier updated → {org.tier}")


def cmd_org_delete(args) -> None:
    _, reg, *_ = _build_services()
    confirm = input(f"Delete org '{args.org_id}'? This is a soft delete. [yes/N]: ")
    if confirm.strip().lower() != "yes":
        print("Aborted.")
        return
    try:
        org = reg.soft_delete(args.org_id)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
    print(f"✅  {args.org_id} soft-deleted (status={org.status.value})")


def cmd_key_generate(args) -> None:
    km, *_ = _build_services()
    expires_at: Optional[int] = None
    if args.expires_days:
        expires_at = int(time.time()) + args.expires_days * 86_400

    token = km.generate(
        tier       = args.tier,
        org_id     = args.org_id,
        issued_at  = int(time.time()),
        expires_at = expires_at,
    )
    parsed = km.validate(token)
    print(f"\n{'=' * 60}")
    print(f"  Generated {args.tier.upper()} key for org: {args.org_id}")
    print(f"\n  {token}\n")
    print(f"  Kid: {parsed.kid}")
    if expires_at:
        print(f"  Expires: {time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime(expires_at))}")
    else:
        print("  Expires: never")
    print(f"{'=' * 60}\n")


def cmd_key_rotate(args) -> None:
    _, reg, ob, *_ = _build_services()
    try:
        result = ob.rotate_key(args.org_id)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
    print(f"\n✅  Key rotated for '{args.org_id}'")
    print(f"\n{'=' * 60}")
    print(f"  NEW API KEY (store securely — shown once):")
    print(f"\n  {result.api_key}\n")
    print(f"  New Kid: {result.kid}")
    print(f"{'=' * 60}\n")
    print("Note: Old key is still valid. Revoke it via the API if needed.")


def cmd_key_verify(args) -> None:
    km, *_ = _build_services()
    try:
        key = km.validate(args.token, current_time=int(time.time()))
    except Exception as exc:
        print(f"❌  Invalid: {exc}", file=sys.stderr)
        sys.exit(1)
    print(f"✅  Valid key")
    _json_out(key.to_public_dict())


def cmd_revenue(args) -> None:
    from runtime.monetization.tier_engine import Tier, ALL_TIERS
    _, reg, *_ = _build_services()
    from runtime.monetization.org_registry import OrgStatus

    orgs   = reg.list_all()
    prices = {t.value: ALL_TIERS[t].monthly_price_usd for t in Tier}
    counts: Dict[str, int] = {"community": 0, "pro": 0, "enterprise": 0}

    for org in orgs:
        if org.status == OrgStatus.ACTIVE:
            counts[org.tier] = counts.get(org.tier, 0) + 1

    mrr = sum(counts.get(t, 0) * prices.get(t, 0.0) for t in counts)
    arr = mrr * 12

    window = args.epoch_window or time.strftime("%Y-%m")
    print(f"\n{'=' * 50}")
    print(f"  💰 InnovativeAI LLC · ADAAD Revenue")
    print(f"  Billing window: {window}")
    print(f"{'=' * 50}")
    print(f"  Estimated MRR:   ${mrr:>10,.2f}")
    print(f"  Estimated ARR:   ${arr:>10,.2f}")
    print(f"{'=' * 50}")
    print(f"  Active orgs by tier:")
    for tier, count in counts.items():
        revenue = count * prices.get(tier, 0.0)
        price_str = f"${prices.get(tier, 0.0):.0f}/mo"
        print(f"    {tier:<14} {count:>4} orgs  × {price_str:<10} = ${revenue:>8,.2f}/mo")
    print(f"{'=' * 50}")
    print(f"  Total active orgs: {sum(counts.values())}")
    print(f"  Grace period:      {sum(1 for o in orgs if o.status.value == 'grace_period')}")
    print(f"  Note: Enterprise custom contracts not included above.")
    print()


def cmd_health(args) -> None:
    version = "unknown"
    try:
        version = (ROOT / "VERSION").read_text().strip()
    except Exception:
        pass

    gate_locked  = os.environ.get("ADAAD_GATE_LOCKED", "false").lower() not in ("", "0", "false", "no")
    signing_key  = bool(os.environ.get("ADAAD_API_SIGNING_KEY"))
    admin_token  = bool(os.environ.get("ADAAD_ADMIN_TOKEN"))
    stripe_wh    = bool(os.environ.get("ADAAD_STRIPE_WEBHOOK_SECRET"))
    github_wh    = bool(os.environ.get("GITHUB_WEBHOOK_SECRET"))

    print(f"\n{'=' * 50}")
    print(f"  ADAAD Platform Health  (v{version})")
    print(f"{'=' * 50}")
    print(f"  Gate locked:         {'🔴 YES' if gate_locked else '🟢 NO'}")
    print(f"  API signing key:     {'🟢 set' if signing_key else '🔴 NOT SET'}")
    print(f"  Admin token:         {'🟢 set' if admin_token else '🔴 NOT SET'}")
    print(f"  Stripe webhook:      {'🟢 set' if stripe_wh else '⚠️  not set'}")
    print(f"  GitHub webhook:      {'🟢 set' if github_wh else '⚠️  not set'}")
    print(f"{'=' * 50}\n")

    if not signing_key:
        print("Action required: set ADAAD_API_SIGNING_KEY to enable API key management.")
    if not admin_token:
        print("Action required: set ADAAD_ADMIN_TOKEN to enable the admin API.")


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="adaad_admin",
        description="ADAAD Admin CLI — InnovativeAI LLC Operations Tool",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # org
    org_p = sub.add_parser("org", help="Organisation management")
    org_sub = org_p.add_subparsers(dest="subcommand", required=True)

    p_create = org_sub.add_parser("create", help="Create an org and provision its first API key")
    p_create.add_argument("--org-id",      required=True)
    p_create.add_argument("--name",        default=None)
    p_create.add_argument("--tier",        default="community", choices=["community", "pro", "enterprise"])
    p_create.add_argument("--expires-days", dest="expires_days", type=int, default=None)

    p_list = org_sub.add_parser("list", help="List organisations")
    p_list.add_argument("--tier",   default=None)
    p_list.add_argument("--status", default=None)

    p_tier = org_sub.add_parser("tier", help="Change an org's tier")
    p_tier.add_argument("--org-id",  required=True)
    p_tier.add_argument("--tier",    required=True, choices=["community", "pro", "enterprise"])
    p_tier.add_argument("--reason",  default="")

    p_delete = org_sub.add_parser("delete", help="Soft-delete an org")
    p_delete.add_argument("--org-id", required=True)

    # key
    key_p = sub.add_parser("key", help="API key management")
    key_sub = key_p.add_subparsers(dest="subcommand", required=True)

    p_keygen = key_sub.add_parser("generate", help="Generate a standalone API key")
    p_keygen.add_argument("--org-id",      required=True)
    p_keygen.add_argument("--tier",        required=True, choices=["community", "pro", "enterprise"])
    p_keygen.add_argument("--expires-days", dest="expires_days", type=int, default=None)

    p_rotate = key_sub.add_parser("rotate", help="Rotate an org's API key")
    p_rotate.add_argument("--org-id", required=True)

    p_verify = key_sub.add_parser("verify", help="Verify an API key token")
    p_verify.add_argument("--token", required=True)

    # revenue
    rev_p = sub.add_parser("revenue", help="Revenue summary")
    rev_p.add_argument("--epoch-window", dest="epoch_window", default=None)

    # health
    sub.add_parser("health", help="Platform health check")

    return parser


def main() -> None:
    parser = build_parser()
    args   = parser.parse_args()

    cmd  = args.command
    sub  = getattr(args, "subcommand", None)

    dispatch = {
        ("org",     "create"):   cmd_org_create,
        ("org",     "list"):     cmd_org_list,
        ("org",     "tier"):     cmd_org_tier,
        ("org",     "delete"):   cmd_org_delete,
        ("key",     "generate"): cmd_key_generate,
        ("key",     "rotate"):   cmd_key_rotate,
        ("key",     "verify"):   cmd_key_verify,
        ("revenue", None):       cmd_revenue,
        ("health",  None):       cmd_health,
    }

    handler = dispatch.get((cmd, sub))
    if handler:
        handler(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
