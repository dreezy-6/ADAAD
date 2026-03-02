# Dependabot Review Policy

This repository uses Dependabot to check dependency updates weekly for Python (`pip`) and GitHub Actions.

## Review expectations

- **Security updates:** prioritize and merge quickly after CI passes.
- **Patch/minor updates:** reviewed as normal maintenance; grouped updates should be reviewed for changelog risks and integration impact.
- **Major updates:** intentionally ignored by default in Dependabot config to reduce churn; handle these as planned, manual upgrade efforts.

## Triage checklist

1. Confirm CI/tests are green.
2. Check release notes for breaking changes and security advisories.
3. Validate lockfile/requirements diff scope matches expected ecosystem.
4. Merge with `dependencies` and `security` labels preserved for tracking.

## Escalation

Escalate to maintainers if:

- CI fails due to transitive breakage.
- The update touches auth, cryptography, policy, or sandbox-critical dependencies.
- The update requires runtime/configuration changes beyond dependency bumping.
