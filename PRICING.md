# ADAAD Pricing

> **Constitutional guarantee:** All tiers run the same GovernanceGate and the same 16-rule constitutional policy engine. Paying more never buys you a weaker gate — it buys you more capacity and more tooling.

---

## Plans

| | **Community** | **Pro** | **Enterprise** |
|---|:---:|:---:|:---:|
| **Price** | Free forever | **$49 / month** | **$499 / month** (custom for large orgs) |
| **Epochs per month** | 50 | 500 | Unlimited |
| **Mutation candidates / epoch** | 3 | 10 | Unlimited |
| **Federation nodes** | — | 3 | Unlimited |
| **API rate limit / min** | 10 | 60 | 600 |
| **Android companion app** | ✅ | ✅ | ✅ |
| **Deterministic replay** | ✅ | ✅ | ✅ |
| **Constitutional gating** | ✅ | ✅ | ✅ |
| **Evidence ledger** | ✅ | ✅ | ✅ |
| **Reviewer reputation engine** | — | ✅ | ✅ |
| **Roadmap self-amendment** | — | ✅ | ✅ |
| **Simulation DSL** | — | ✅ | ✅ |
| **Aponi IDE integration** | — | ✅ | ✅ |
| **Webhook integrations** | — | ✅ | ✅ |
| **Audit export** | — | ✅ | ✅ |
| **SSO / SAML** | — | — | ✅ |
| **99.9% SLA guarantee** | — | — | ✅ |
| **Priority support** | — | — | ✅ |
| **Custom constitutional rules** | — | — | ✅ |
| **Dedicated onboarding** | — | — | ✅ |

---

## Community — Free forever

Open-source. Self-hosted. No credit card.

ADAAD is MIT-licensed and the Community plan gives you the full governance engine: constitutional gating, deterministic replay, evidence ledger, and the Android companion app. The limits exist to support sustainable infrastructure — not to degrade the governance quality.

**Get started:**
```bash
git clone https://github.com/InnovativeAI-adaad/ADAAD.git
cd ADAAD && python onboard.py
```

---

## Pro — $49 / month

For individual engineers and small teams who need the full ADAAD governance suite without infrastructure overhead.

**What unlocks at Pro:**
- **Reviewer Reputation Engine** — Adaptive calibration of governance pressure based on reviewer track records.
- **Roadmap Self-Amendment** — The engine proposes changes to its own roadmap; humans approve. No auto-merge.
- **Simulation DSL** — Replay historical epochs under hypothetical governance constraints, zero side-effects.
- **Aponi IDE Integration** — Inline evidence viewer, mutation proposal panel, and replay inspector.
- **Webhook Integrations** — Push governance events to Slack, PagerDuty, Jira, or any webhook endpoint.
- **Audit Export** — Export signed evidence bundles for compliance, auditors, or external review.
- **Up to 3 Federation Nodes** — Govern mutations across up to 3 repositories simultaneously.

**Start Pro:**
→ [innovativeai.io/adaad/upgrade?plan=pro](https://innovativeai.io/adaad/upgrade?plan=pro)

---

## Enterprise — From $499 / month

For organizations that need scale, compliance, and guaranteed SLAs.

**What unlocks at Enterprise:**
- **Unlimited epochs, federation nodes, and mutation candidates.**
- **SSO / SAML** — Integrate with Okta, Azure AD, or any SAML 2.0 provider.
- **99.9% Uptime SLA** — Contractual availability guarantee.
- **Priority Support** — Dedicated Slack channel + 4-hour response SLA.
- **Custom Constitutional Rules** — Extend the base 16-rule constitution with organization-specific governance rules.
- **Dedicated Onboarding** — White-glove setup, integration with your existing CI/CD, and governance training.

**Contact sales:**
→ [innovativeai.io/adaad/enterprise](https://innovativeai.io/adaad/enterprise)
→ Email: enterprise@innovativeai.io

---

## FAQ

**Can I self-host Pro or Enterprise?**
Yes. All tiers are self-hostable. Pro and Enterprise require a valid API key (generated at sign-up) which the server validates offline via HMAC signature — no phone-home required.

**What counts as an epoch?**
One complete cycle of the mutation pipeline: propose → simulate → replay-verify → constitutional gate → execute (or halt).

**What happens if I exceed my epoch quota?**
The API returns `429 Quota Exceeded` with an upgrade URL. In-progress epochs are never halted mid-run — the quota check fires before the epoch begins.

**Is the governance gate weakened at higher tiers?**
Never. Constitutional gating is architecturally invariant across all tiers. Paying more does not buy a softer gate — it buys more capacity.

**Can I migrate from Community to Pro without downtime?**
Yes. Upgrade at any time; the API key is updated immediately. Evidence and epoch history are preserved.

**Do you offer academic or non-profit discounts?**
Yes — contact enterprise@innovativeai.io with your affiliation.

---

## API Keys

Every paid plan generates an ADAAD API key used for:
1. Authenticating API requests (`Authorization: Bearer <key>`)
2. Tier enforcement and rate limiting
3. Usage metering per billing period

Keys are HMAC-SHA256 signed bearer tokens — no database lookup required for validation. They can be rotated without downtime.

**Key format:**
```
adaad_<tier_prefix>_<base64url_payload>_<hmac_tag>
```

Where `tier_prefix` is `cm` (Community), `pr` (Pro), or `en` (Enterprise).

---

*Pricing is subject to change with 30 days notice for existing subscribers.*
*All prices in USD. Enterprise custom pricing available for 10+ node deployments.*

**InnovativeAI LLC · Blackwell, Oklahoma · Founded by Dustin L. Reid**
