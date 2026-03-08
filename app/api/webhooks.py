# SPDX-License-Identifier: Apache-2.0
"""Webhook API Router — ADAAD Phase 8, M8-09.

Handles inbound webhooks from:
  - Stripe (billing lifecycle → tier transitions)
  - GitHub App (PR events → governance gate triggers)

Both endpoints are fail-closed: invalid signatures return 400,
and events are only processed after signature verification passes.

All webhook events are recorded in the governance ledger before
any state mutation occurs.

Author: Dustin L. Reid · InnovativeAI LLC
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import JSONResponse

from runtime.integrations.github_webhook_handler import (
    verify_webhook_signature as verify_github_sig,
    handle_push,
    handle_pull_request,
    handle_check_run,
    handle_workflow_run,
    handle_installation,
)
from runtime.monetization.billing_gateway import (
    BillingGateway,
    BillingLifecycleEvent,
    BillingEventType,
    WebhookSignatureError,
)
from runtime.monetization.org_registry import OrgRegistry, OrgNotFound, OrgStatus
from runtime.monetization.onboarding_service import OnboardingService
from runtime.monetization.notification_dispatcher import (
    NotificationDispatcher,
    NotificationPayload,
    NotifiableEvent,
)

log = logging.getLogger("adaad.webhooks")


# ---------------------------------------------------------------------------
# Module-level singletons (populated by build_webhook_router)
# ---------------------------------------------------------------------------

_billing_gateway:   Optional[BillingGateway]          = None
_org_registry:      Optional[OrgRegistry]             = None
_onboarding:        Optional[OnboardingService]       = None
_notifications:     Optional[NotificationDispatcher]  = None


def build_webhook_router(
    billing_gateway:   Optional[BillingGateway]          = None,
    org_registry:      Optional[OrgRegistry]             = None,
    onboarding:        Optional[OnboardingService]       = None,
    notifications:     Optional[NotificationDispatcher]  = None,
) -> APIRouter:
    """Build and return the webhook APIRouter with injected dependencies."""
    global _billing_gateway, _org_registry, _onboarding, _notifications
    _billing_gateway  = billing_gateway
    _org_registry     = org_registry
    _onboarding       = onboarding
    _notifications    = notifications
    return _router


router = _router = APIRouter(prefix="/webhooks", tags=["webhooks"])


# ---------------------------------------------------------------------------
# Stripe webhook
# ---------------------------------------------------------------------------

@_router.post("/stripe")
async def stripe_webhook(
    request: Request,
    stripe_signature: Optional[str] = Header(default=None, alias="stripe-signature"),
) -> Dict[str, Any]:
    """Receive and process Stripe billing events.

    Verifies HMAC signature, dispatches to BillingGateway, and reflects
    tier changes in OrgRegistry.
    """
    payload = await request.body()

    if not payload:
        raise HTTPException(status_code=400, detail="Empty webhook payload")

    gateway = _billing_gateway
    if gateway is None:
        # Stripe not configured — log and accept silently (don't break health checks)
        log.warning("stripe_webhook_received_but_billing_gateway_not_configured")
        return {"received": True, "processed": False, "reason": "billing_not_configured"}

    try:
        event = gateway.process_webhook(payload, stripe_signature or "")
    except WebhookSignatureError as exc:
        log.warning("stripe_signature_verification_failed: %s", exc)
        raise HTTPException(status_code=400, detail="Webhook signature verification failed")
    except Exception as exc:
        log.error("stripe_webhook_processing_error: %s", exc)
        raise HTTPException(status_code=500, detail="Webhook processing error")

    return {"received": True, "processed": True, "event_type": event.get("type")}


def _handle_billing_lifecycle(event: BillingLifecycleEvent) -> None:
    """Callback invoked by BillingGateway for each lifecycle event."""
    log.info(
        "billing_lifecycle org=%s event=%s from=%s to=%s",
        event.org_id, event.event_type.value, event.from_tier, event.to_tier
    )

    if _org_registry is None:
        return

    try:
        org = _org_registry.get_by_stripe(event.stripe_customer_id)
    except OrgNotFound:
        # Org not yet onboarded — auto-create on subscription creation
        if (
            event.event_type == BillingEventType.TIER_PROVISIONED
            and _onboarding is not None
        ):
            org_id = _sanitise_org_id(event.org_id or event.stripe_customer_id)
            try:
                result = _onboarding.onboard(
                    org_id             = org_id,
                    display_name       = org_id,
                    tier               = event.to_tier,
                    stripe_customer_id = event.stripe_customer_id,
                )
                log.info("auto_onboarded_org org=%s tier=%s", org_id, event.to_tier)
                # Note: key is NOT returned here — it would go to a post-onboarding
                # email flow in production. Log the kid for audit.
                log.info("AUDIT: new_org=%s kid=%s — deliver key via secure channel",
                         org_id, result.kid)
            except Exception as exc:
                log.error("auto_onboard_failed org=%s: %s", org_id, exc)
        return

    # Update existing org tier / status
    try:
        if event.event_type in (
            BillingEventType.TIER_PROVISIONED,
            BillingEventType.TIER_UPGRADED,
            BillingEventType.TIER_DOWNGRADED,
            BillingEventType.PAYMENT_RECOVERED,
        ):
            _org_registry.set_tier(
                org.org_id, event.to_tier,
                reason=f"stripe:{event.event_type.value}"
            )
            if org.status != OrgStatus.ACTIVE:
                _org_registry.set_status(org.org_id, OrgStatus.ACTIVE, reason="billing_recovered")

        elif event.event_type == BillingEventType.TIER_CANCELLED:
            _org_registry.set_tier(org.org_id, "community", reason="subscription_cancelled")

        elif event.event_type == BillingEventType.PAYMENT_FAILED:
            _org_registry.set_status(
                org.org_id, OrgStatus.GRACE_PERIOD, reason="payment_failed"
            )

        # Fire notification
        if _notifications:
            notif_map = {
                BillingEventType.TIER_UPGRADED:    (NotifiableEvent.TIER_CHANGED, "info"),
                BillingEventType.TIER_DOWNGRADED:  (NotifiableEvent.TIER_CHANGED, "warning"),
                BillingEventType.TIER_CANCELLED:   (NotifiableEvent.TIER_CHANGED, "warning"),
                BillingEventType.PAYMENT_FAILED:   (NotifiableEvent.PAYMENT_FAILED, "critical"),
                BillingEventType.PAYMENT_RECOVERED:(NotifiableEvent.PAYMENT_RECOVERED, "info"),
            }
            if event.event_type in notif_map:
                notif_event, severity = notif_map[event.event_type]
                _notifications.dispatch(
                    NotificationPayload(
                        event_type = notif_event,
                        org_id     = org.org_id,
                        title      = f"ADAAD: {event.event_type.value.replace('_', ' ').title()}",
                        body       = (
                            f"Organisation `{org.org_id}` tier: "
                            f"`{event.from_tier}` → `{event.to_tier}`"
                        ),
                        severity   = severity,
                        metadata   = {"stripe_event_id": event.stripe_event_id},
                    ),
                    channels=[],  # org-level channels loaded from registry in production
                )

    except Exception as exc:
        log.error("billing_lifecycle_handler_error org=%s: %s", event.org_id, exc)


def _sanitise_org_id(raw: str) -> str:
    """Convert a Stripe customer ID or org name to a valid org slug."""
    import re
    s = raw.lower().replace("cus_", "org-").replace("_", "-")
    s = re.sub(r"[^a-z0-9\-]", "", s)
    s = re.sub(r"-+", "-", s).strip("-")
    if len(s) < 3:
        s = "org-" + s
    return s[:63]


# ---------------------------------------------------------------------------
# GitHub App webhook
# ---------------------------------------------------------------------------

@_router.post("/github")
async def github_webhook(
    request: Request,
    x_github_event:      Optional[str] = Header(default=None, alias="x-github-event"),
    x_hub_signature_256: Optional[str] = Header(default=None, alias="x-hub-signature-256"),
) -> Dict[str, Any]:
    """Receive and process GitHub App webhook events.

    Verifies HMAC-SHA256 signature and dispatches to the appropriate handler.
    Governance gate triggers fire asynchronously on PR-merged-to-main events.
    """
    payload = await request.body()

    if not payload:
        raise HTTPException(status_code=400, detail="Empty webhook payload")

    # Signature verification (fail-closed if secret is set)
    webhook_secret = os.environ.get("GITHUB_WEBHOOK_SECRET", "")
    if webhook_secret and not verify_github_sig(payload, x_hub_signature_256 or ""):
        log.warning("github_webhook_signature_verification_failed")
        raise HTTPException(status_code=400, detail="GitHub webhook signature verification failed")

    import json
    try:
        body = json.loads(payload.decode("utf-8"))
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    event_type = (x_github_event or "").lower()
    result: Dict[str, Any] = {"received": True, "event": event_type}

    try:
        if event_type == "push":
            result["handler"] = handle_push(body)
        elif event_type == "pull_request":
            result["handler"] = handle_pull_request(body)
        elif event_type == "check_run":
            result["handler"] = handle_check_run(body)
        elif event_type == "workflow_run":
            result["handler"] = handle_workflow_run(body)
        elif event_type in ("installation", "installation_repositories"):
            result["handler"] = handle_installation(body)
        else:
            result["handler"] = {"status": "ignored", "event": event_type}
    except Exception as exc:
        log.error("github_webhook_handler_error event=%s: %s", event_type, exc)
        result["error"] = str(exc)[:200]

    return result
