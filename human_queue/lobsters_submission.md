# Lobste.rs Submission — Human Queue

> Lobste.rs is invite-only and highly curated. Posts here are high signal-to-noise.
> Must post from a verified account. If you don't have one, request an invite.

## Submission

**Title:** ADAAD: Constitutional governance for autonomous code mutation (MIT, Python)
**URL:** https://github.com/InnovativeAI-adaad/ADAAD
**Tags:** ai, python, open-source, devtools, security, programming

## Comment to post after submission

```
I built this because I kept running into the same problem: every AI coding tool 
can suggest code, but none of them can prove the suggestion was safe or produce
an auditable decision trail.

ADAAD's approach: three Claude agents compete via genetic algorithm, and every 
candidate must pass a 16-rule constitutional gate before execution. One blocking 
failure = full halt. Every decision is SHA-256 hash-chained and deterministically 
replayable — re-run any past epoch months later and prove byte-identical outputs.

The governance gate is architectural, not configurable. It can't be overridden 
by any agent, operator, or configuration flag.

Community tier is free forever (MIT, self-hosted). Code: https://github.com/InnovativeAI-adaad/ADAAD

Happy to answer questions about the constitutional model or the deterministic 
replay architecture — those are the parts I'm most proud of technically.
```
