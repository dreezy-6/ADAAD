# ADAAD Enterprise Deployment Guide

> **Audience:** Enterprise customers deploying ADAAD for multi-team, multi-repository, or compliance-sensitive environments.

---

## Architecture overview

```
                    ┌───────────────────────────────────────┐
                    │         Your CI/CD Pipeline           │
                    │                                       │
                    │   PR opened → ADAAD governance gate   │
                    │   Pass → merge allowed                │
                    │   Fail → merge blocked                │
                    └──────────────────┬────────────────────┘
                                       │
                    ┌──────────────────▼────────────────────┐
                    │        ADAAD Enterprise Server        │
                    │                                       │
                    │  ┌─────────────────────────────────┐  │
                    │  │  Monetization Middleware         │  │
                    │  │  (API key auth · tier checks)    │  │
                    │  └──────────────┬──────────────────┘  │
                    │                 │                      │
                    │  ┌──────────────▼──────────────────┐  │
                    │  │  Constitutional Gate             │  │
                    │  │  (16 rules · fail-closed)        │  │
                    │  └──────────────┬──────────────────┘  │
                    │                 │                      │
                    │  ┌──────────────▼──────────────────┐  │
                    │  │  Evidence Ledger                 │  │
                    │  │  (SHA-256 hash-chained)          │  │
                    │  └─────────────────────────────────┘  │
                    └───────────────────────────────────────┘
                                       │
            ┌──────────────────────────┼──────────────────────────┐
            ▼                          ▼                          ▼
    ┌───────────────┐         ┌─────────────────┐        ┌──────────────┐
    │  Federation   │         │  Reviewer Rep   │        │  Aponi IDE   │
    │  Node A       │         │  Dashboard      │        │  (Operators) │
    └───────────────┘         └─────────────────┘        └──────────────┘
```

---

## Prerequisites

| Requirement | Version |
|---|---|
| Python | 3.11.9 (pinned) |
| pip | ≥ 23.0 |
| git | ≥ 2.40 |
| Docker (optional) | ≥ 24.0 |
| Redis (optional, recommended) | ≥ 7.0 |

---

## 1. Installation

```bash
git clone https://github.com/InnovativeAI-adaad/ADAAD.git
cd ADAAD
python onboard.py
```

`onboard.py` performs: Python version check → virtualenv → dependency install → schema validation → governed dry-run.

---

## 2. Environment configuration

Create a `.env` file (never commit this):

```env
# --- Required ---
ADAAD_ENV=production
ADAAD_CLAUDE_API_KEY=<your_anthropic_key>
ADAAD_SIGNING_KEY=<32-byte hex signing key>

# --- Monetization (Enterprise) ---
ADAAD_API_SIGNING_KEY=<signing key for API bearer tokens>
ADAAD_STRIPE_WEBHOOK_SECRET=<whsec_...>
ADAAD_STRIPE_PRICE_PRO=<price_...>
ADAAD_STRIPE_PRICE_ENTERPRISE=<price_...>

# --- Federation (Enterprise) ---
ADAAD_FEDERATION_HMAC_KEY=<min 32-byte hex key>
ADAAD_NODE_ID=<stable node identifier>

# --- SSO / SAML (Enterprise) ---
ADAAD_SAML_METADATA_URL=<your_idp_metadata_url>
ADAAD_SAML_SP_ENTITY_ID=adaad-<your-org>

# --- Optional tuning ---
ADAAD_ROADMAP_AMENDMENT_TRIGGER_INTERVAL=10
ADAAD_GATE_LOCKED=false
```

---

## 3. API key provisioning

Enterprise API keys are provisioned via the InnovativeAI admin portal or via the `tools/adaad_audit.py` script:

```bash
# Generate an enterprise API key for org "acme-corp"
python tools/adaad_audit.py generate-key \
    --tier enterprise \
    --org-id acme-corp \
    --issued-at $(date +%s)
```

Output:
```
adaad_en_eyJ2IjoiMSIsImtpZCI6IjE2Y2hhciJ9..._<hmac_tag>
```

Distribute this key to your team via your secrets manager (AWS Secrets Manager, HashiCorp Vault, etc.).

Keys are validated offline (no database call). Rotation is zero-downtime: issue a new key, update secrets, revoke the old kid via the admin API.

---

## 4. SSO / SAML configuration

Enterprise tier includes SAML 2.0 SSO integration. Configure your Identity Provider (Okta, Azure AD, etc.) with:

| Field | Value |
|---|---|
| SP Entity ID | `adaad-<your-org>` |
| ACS URL | `https://<your-adaad-host>/auth/saml/acs` |
| Metadata URL | `https://<your-adaad-host>/auth/saml/metadata` |
| Name ID Format | `urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress` |

After IDP configuration, set `ADAAD_SAML_METADATA_URL` to your IDP's metadata endpoint and restart the server.

---

## 5. Federation setup

Multi-node federation allows ADAAD to govern mutations across multiple repositories simultaneously. Each node must:

1. Have a valid Enterprise API key.
2. Share the same `ADAAD_FEDERATION_HMAC_KEY` (rotated via the runbook at `docs/runbooks/hmac_key_rotation.md`).
3. Be resolvable by peer nodes (hostname or IP + port).

```bash
# Register a peer node
python tools/adaad_audit.py federation register \
    --node-id node-b \
    --endpoint https://adaad-node-b.internal:8080
```

Federation invariant: `divergence_count == 0` is required before any mutation propagates to a peer node. Any divergence blocks promotion and is logged in the evidence ledger.

---

## 6. Custom constitutional rules

Enterprise customers may extend the base 16-rule constitution with organization-specific governance rules.

Rules are defined in YAML and added to `runtime/governance/constitution.yaml`:

```yaml
- id: org_license_header
  tier: 1
  enforcement: blocking
  rationale: >
    All files must carry the approved ACME Corp SPDX license header.
    Missing or incorrect headers block mutation promotion.
  validator: org_license_header_validator
```

Implement the validator in `runtime/governance/validators/`:

```python
# runtime/governance/validators/org_license_header.py
from runtime.governance.validators.base import BaseValidator

class OrgLicenseHeaderValidator(BaseValidator):
    rule_id = "org_license_header"
    tier    = 1
    enforcement = "blocking"

    def validate(self, mutation_request) -> dict:
        # ... your validation logic
        return {"passed": True, "evidence": {...}}
```

Custom rules follow the same determinism, replay-safety, and fail-closed requirements as built-in rules. The constitutional test suite (`tests/governance/inviolability/`) validates custom rules on every CI run.

---

## 7. Monitoring and observability

### Governance endpoints

| Endpoint | Description |
|---|---|
| `GET /health` | Server health (no auth) |
| `GET /governance/reviewer-calibration` | Reviewer reputation summary |
| `GET /api/monetization/usage/{org_id}` | Usage by billing period |
| `GET /api/monetization/tiers` | Tier capability catalogue |

### Evidence ledger

Every governed decision is recorded in the append-only evidence ledger at `security/ledger/`. The ledger is SHA-256 hash-chained — any tampering is detectable.

Export for external audit:
```bash
python tools/adaad_audit.py export-evidence \
    --format jsonl \
    --output evidence-export-$(date +%Y%m%d).jsonl
```

### Webhook events

Configure outbound webhooks in your `.env` to push governance events to Slack, PagerDuty, or any HTTP endpoint:

```env
ADAAD_WEBHOOK_URL=https://hooks.slack.com/...
ADAAD_WEBHOOK_EVENTS=mutation_approved,mutation_rejected,gate_halt
```

---

## 8. SLA and support

| Tier | Uptime SLA | Response time | Channel |
|---|---|---|---|
| Community | Best-effort | — | GitHub Issues |
| Pro | Best-effort | Business hours | Email |
| Enterprise | **99.9%** | **4 hours** | Dedicated Slack + Email |

Enterprise support: enterprise@innovativeai.io

**InnovativeAI LLC · Blackwell, Oklahoma · Founded by Dustin L. Reid**
