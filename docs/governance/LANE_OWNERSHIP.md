# ADAAD Lane Ownership Register

This register identifies accountable owners for each strategic build lane.
Update in the same change set when lane ownership changes.

| Lane | Owner | Backup owner | Escalation path |
| --- | --- | --- | --- |
| Contract | Governance Maintainer | Release Maintainer | Architecture Review Council |
| Determinism | Runtime Determinism Maintainer | Governance Maintainer | Architecture Review Council |
| Security | Security Maintainer | Governance Maintainer | Security Incident Commander |
| Secret-scanning | Security Maintainer | CI Maintainer | Security Incident Commander |
| Evidence | Release Maintainer | Governance Maintainer | Release Governance Board |
| Documentation | Docs Maintainer | Release Maintainer | Architecture Review Council |

## Ownership invariants

- Every required lane in `docs/ADAAD_STRATEGIC_BUILD_SUGGESTIONS.md` must map to exactly one primary owner.
- Every lane owner is responsible for triaging and dispositioning failed gates in their lane.
- Ownership updates are governance-surface changes and must include release/docs alignment updates.
