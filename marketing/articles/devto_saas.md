# From MIT open-source to SaaS: how InnovativeAI monetized a governed AI devtool

*Community free forever. Pro at $49/mo. Enterprise at $499/mo. The constitution protects every tier equally.*

---

I launched ADAAD as fully open-source (MIT) with a free Community tier. Then I added a paid SaaS layer on top. Here's the full architecture of how the monetization works — and why the governance model is actually the strongest argument for paying.

## The founding constraint

ADAAD's constitution includes one rule that governs the entire pricing model:

> **Paying more never weakens the constitutional gate. It buys capacity and tooling.**

This isn't marketing copy. It's enforced architecturally. The `TierEngine.check_capability()` function gates features *above* the GovernanceGate in the call stack. You can get more epochs, more candidates, more federation nodes. You cannot get a softer governance rule.

```python
# Tier capability check is pure — no I/O, replay-safe
result = tier_engine.check_capability(
    org_id=org.id,
    capability="roadmap_amendment",
    tier=Tier.PRO,
)
# Returns: CapabilityResult(allowed=True, tier_required=Tier.PRO)
```

The governance gate sits downstream of this. It evaluates identically regardless of what `check_capability` returned.

## What the tiers actually give you

**Community (free forever):**
- Full 16-rule constitutional gate — identical to Pro and Enterprise
- 50 epochs/month, 3 candidates/epoch
- Evidence ledger, deterministic replay, Android app
- Self-hosted, MIT, no telemetry

**Pro ($49/month):**
- 500 epochs/month, 10 candidates/epoch
- Reviewer Reputation Engine — adaptive governance pressure based on reviewer track records
- Simulation DSL — replay historical epochs under hypothetical constraints
- Roadmap Self-Amendment — the engine proposes changes to its own roadmap
- Aponi IDE integration — inline evidence viewer, mutation panel
- Webhook integrations (Slack, PagerDuty, Jira)
- Signed audit export for compliance reviews

**Enterprise ($499/month):**
- Unlimited epochs, candidates, federation nodes
- Custom constitutional rules — extend the 16-rule base with org-specific governance
- SSO/SAML (Okta, Azure AD)
- 99.9% SLA, 4-hour priority support
- Dedicated onboarding and governance training

## The API key architecture

Every paid tier generates an HMAC-SHA256 bearer token:

```
adaad_pr_<base64url_payload>_<hmac_tag>
```

Validation is offline — no database lookup required, making it replay-safe. The tier is encoded in the prefix (`cm`, `pr`, `en`). Keys can be rotated without downtime.

## Why governance is the monetization argument

The Pro and Enterprise features aren't governance improvements. They're productivity multipliers *on top of* governance that already works. This is the right structure:

1. Community users trust the product because governance is complete at the free tier
2. Pro users pay because they need *more* of a thing they already trust
3. Enterprise users pay for compliance guarantees, custom rules, and SLAs around a system they've validated works

The governance moat is also the sales moat. You can't just switch to a competitor — nobody else has an auditable evidence ledger, deterministic replay, or a constitutional gate. Switching cost is high by design, but for the right reason: we're the only ones who built this properly.

## Current status

ADAAD has shipped 12 phases across 900+ commits. The SaaS layer (Phase 8) is production-grade today: TierEngine, API key manager, usage tracker, Stripe billing, FastAPI middleware with sliding-window rate limiting.

Community tier: free forever, MIT.  
Pro: [innovativeai.io/adaad/upgrade?plan=pro](https://innovativeai.io/adaad/upgrade?plan=pro)  
Enterprise: enterprise@innovativeai.io

---

**GitHub:** https://github.com/InnovativeAI-adaad/ADAAD  
**Author:** Dustin L. Reid · Founder, InnovativeAI LLC · Blackwell, Oklahoma
