# Codex Setup for ADAAD Governed Build Agent

This runbook provides the discovery path and installation checklist for enabling
Codex with the ADAAD governed build-agent contract.

## Source-of-truth files

- Agent contract: `AGENTS.md` (repository root).
- Strategic build model: `docs/ADAAD_STRATEGIC_BUILD_SUGGESTIONS.md`.
- Lane ownership register: `docs/governance/LANE_OWNERSHIP.md`.

## System prompt location policy

The full Codex system prompt content may be maintained outside this repository
(for example in a Codex admin console or private operator runbook).

When prompt text is maintained outside git, this file is the required discovery
entry point and must document:

1. where the authoritative prompt is stored,
2. who can update it,
3. when it was last synchronized with `AGENTS.md`.

## Installation checklist

- [ ] `AGENTS.md` is present at repository root.
- [ ] Codex has read access to the full ADAAD repository tree.
- [ ] `.adaad_agent_state.json` is ignored via `.gitignore`.
- [ ] `.adaad_operator_contacts.json` (if used) is local-only and never committed.
- [ ] `docs/governance/LANE_OWNERSHIP.md` has current lane owners.
- [ ] First invocation test executed with `ADAAD status`.

## Operator note

Changes to trigger contracts, gate order, or workflow semantics in `AGENTS.md`
should be followed by a Codex prompt synchronization check in the same change
window.
