# SPDX-License-Identifier: Apache-2.0
"""Stripe Checkout Router — ADAAD Phase 8, M8-12.

Creates Stripe Checkout sessions for Pro and Enterprise upgrades.
This is the server-side half of the conversion funnel — the frontend
calls POST /api/checkout/session and gets back a Stripe-hosted URL
to redirect the user to.

Flow:
  1. User clicks "Upgrade to Pro" on the pricing page
  2. Frontend calls POST /api/checkout/session {plan: "pro", org_id: "..."}
  3. Server creates Stripe Checkout session
  4. Server returns {url: "https://checkout.stripe.com/..."}
  5. Frontend redirects to Stripe
  6. User completes payment
  7. Stripe fires customer.subscription.created webhook → /webhooks/stripe
  8. BillingGateway handles it → OrgRegistry tier transition
  9. User lands on /api/checkout/success?session_id=... → org confirmed active

Author: Dustin L. Reid · InnovativeAI LLC
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

log = logging.getLogger("adaad.checkout")

STRIPE_SUCCESS_URL  = os.environ.get(
    "ADAAD_STRIPE_SUCCESS_URL",
    "https://innovativeai.io/adaad/welcome?session_id={CHECKOUT_SESSION_ID}"
)
STRIPE_CANCEL_URL   = os.environ.get(
    "ADAAD_STRIPE_CANCEL_URL",
    "https://innovativeai.io/adaad/upgrade?cancelled=1"
)


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------

class CheckoutSessionRequest(BaseModel):
    plan:   str   # "pro" | "enterprise"
    org_id: str
    email:  Optional[str] = None


# ---------------------------------------------------------------------------
# Router factory
# ---------------------------------------------------------------------------

def build_checkout_router() -> APIRouter:
    router = APIRouter(prefix="/api/checkout", tags=["checkout"])

    @router.post("/session")
    def create_checkout_session(body: CheckoutSessionRequest) -> Dict[str, Any]:
        """Create a Stripe Checkout session and return the hosted URL.

        Requires ADAAD_STRIPE_SECRET_KEY, ADAAD_STRIPE_PRICE_PRO,
        ADAAD_STRIPE_PRICE_ENTERPRISE to be set.
        """
        stripe_secret  = os.environ.get("ADAAD_STRIPE_SECRET_KEY", "")
        price_pro      = os.environ.get("ADAAD_STRIPE_PRICE_PRO", "")
        price_ent      = os.environ.get("ADAAD_STRIPE_PRICE_ENTERPRISE", "")

        if not stripe_secret:
            raise HTTPException(
                status_code=503,
                detail="Checkout not configured: contact support@innovativeai.io",
            )

        if body.plan not in ("pro", "enterprise"):
            raise HTTPException(status_code=422, detail=f"Unknown plan: {body.plan!r}")

        price_id = price_pro if body.plan == "pro" else price_ent
        if not price_id:
            raise HTTPException(
                status_code=503,
                detail=f"Plan '{body.plan}' price not configured. Contact support.",
            )

        try:
            import urllib.request, urllib.parse, json, base64

            payload = urllib.parse.urlencode({
                "mode":                          "subscription",
                "line_items[0][price]":          price_id,
                "line_items[0][quantity]":       "1",
                "subscription_data[metadata][adaad_org_id]": body.org_id,
                "metadata[adaad_org_id]":        body.org_id,
                "success_url":                   STRIPE_SUCCESS_URL,
                "cancel_url":                    STRIPE_CANCEL_URL,
                **({"customer_email": body.email} if body.email else {}),
            }).encode()

            credentials = base64.b64encode(f"{stripe_secret}:".encode()).decode()
            req = urllib.request.Request(
                "https://api.stripe.com/v1/checkout/sessions",
                data    = payload,
                headers = {
                    "Authorization":  f"Basic {credentials}",
                    "Content-Type":   "application/x-www-form-urlencoded",
                    "Stripe-Version": "2023-10-16",
                },
                method = "POST",
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode())

            log.info(
                "checkout_session_created org=%s plan=%s session=%s",
                body.org_id, body.plan, data.get("id")
            )
            return {
                "session_id": data["id"],
                "url":        data["url"],
                "plan":       body.plan,
                "org_id":     body.org_id,
            }

        except HTTPException:
            raise
        except Exception as exc:
            log.error("checkout_session_error org=%s plan=%s: %s", body.org_id, body.plan, exc)
            raise HTTPException(
                status_code=502,
                detail="Checkout session creation failed. Try again or contact support@innovativeai.io",
            )

    @router.get("/success")
    def checkout_success(session_id: str = "") -> Dict[str, Any]:
        """Landing endpoint after successful Stripe checkout.

        Confirms the session and returns org status. The actual tier
        transition happens asynchronously via the Stripe webhook.
        """
        if not session_id:
            raise HTTPException(status_code=400, detail="Missing session_id")
        return {
            "status":  "success",
            "message": "Payment received! Your ADAAD tier is being activated.",
            "session_id": session_id,
            "next":    "Your API key will be delivered to your registered email within 2 minutes.",
            "support": "support@innovativeai.io",
            "docs":    "https://innovativeai.io/adaad/docs/quickstart",
        }

    @router.get("/portal")
    def customer_portal(stripe_customer_id: str = "") -> Dict[str, Any]:
        """Create a Stripe Customer Portal session for self-serve billing management."""
        stripe_secret  = os.environ.get("ADAAD_STRIPE_SECRET_KEY", "")
        if not stripe_secret or not stripe_customer_id:
            raise HTTPException(
                status_code=503,
                detail="Billing portal not available. Contact support@innovativeai.io",
            )

        try:
            import urllib.request, urllib.parse, json, base64

            payload = urllib.parse.urlencode({
                "customer":   stripe_customer_id,
                "return_url": os.environ.get(
                    "ADAAD_STRIPE_PORTAL_RETURN_URL",
                    "https://innovativeai.io/adaad/settings/billing"
                ),
            }).encode()

            credentials = base64.b64encode(f"{stripe_secret}:".encode()).decode()
            req = urllib.request.Request(
                "https://api.stripe.com/v1/billing_portal/sessions",
                data    = payload,
                headers = {
                    "Authorization":  f"Basic {credentials}",
                    "Content-Type":   "application/x-www-form-urlencoded",
                    "Stripe-Version": "2023-10-16",
                },
                method = "POST",
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode())

            return {"url": data["url"]}

        except HTTPException:
            raise
        except Exception as exc:
            log.error("customer_portal_error cus=%s: %s", stripe_customer_id, exc)
            raise HTTPException(status_code=502, detail="Portal session creation failed.")

    return router
