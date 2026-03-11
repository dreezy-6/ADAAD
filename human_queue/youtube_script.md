# YouTube Script — ADAAD Demo Video

## Video: "I built an AI that governs itself — here's how it works" (8-12 min)

**Target:** Developers, AI practitioners, compliance-focused engineers  
**Thumbnail text:** "AI that PROVES what it changed"  
**Thumbnail visual:** Terminal output showing GovernanceGate PASS / HALT split screen

---

### HOOK (0:00–0:30)

[Screen: GitHub Copilot logo → build failure → no audit trail]

"When GitHub Copilot breaks your build — and it will — you have no audit trail. You can't answer: what changed? Was it tested the same way twice? Why did the AI think this was safe?

I got tired of that problem. So I built ADAAD."

---

### WHAT IS ADAAD (0:30–2:00)

[Screen: ADAAD GitHub repo landing page]

"ADAAD stands for Autonomous Device-Anchored Adaptive Development. It's an open-source system where three AI agents compete to improve your codebase — and every proposed change must pass a 16-rule constitutional governance gate before a single byte changes.

It's free. MIT licensed. Self-hosted. And it can prove what it did."

---

### THE THREE AGENTS (2:00–3:30)

[Screen: Split terminal showing 3 agents proposing]

"Three agents. Architect, Dream, and Beast. Each is a distinct Claude system prompt with a different focus.

Architect hunts for structural problems — dependency cleanup, interface contracts.
Dream goes lateral — novel approaches, experimental rewrites.
Beast is pure performance — throughput, complexity reduction.

They see the same codebase. They produce different proposals. They compete."

---

### THE GENETIC ALGORITHM (3:30–5:00)

[Screen: Population manager visualization]

"Proposals enter a genetic algorithm. Candidates cross, mutate, and compete across generations. BLX-alpha crossover. UCB1 bandit agent selection. Elite preservation.

The fittest candidates survive to the constitutional gate."

---

### THE GOVERNANCE GATE (5:00–7:30)

[Screen: Terminal showing BLOCK vs PASS]

"This is what makes ADAAD categorically different.

16 deterministic rules. Evaluated in strict order. One blocking failure: full halt. Named failure mode written to the evidence ledger. No exceptions."

[Show code: GovernanceGate.evaluate()]

"The GovernanceGate is the only surface that can approve a mutation. It cannot be overridden by any agent, bypassed by configuration, or weakened by a higher pricing tier.

Let me show you what a governance halt looks like in real-time..."

[Demo: trigger a governance halt, show the evidence record]

---

### DETERMINISTIC REPLAY (7:30–9:00)

[Screen: --replay audit running]

"Every approved mutation is SHA-256 hash-chained into an append-only evidence ledger. Signed. Permanent.

Months later, you can re-run any epoch and prove byte-for-byte that the exact same inputs produced the exact same outputs. Divergence from the original halts the process and shows you exactly what changed."

[Demo: replay audit on a past epoch]

---

### HOW TO START (9:00–10:00)

[Screen: pip install adaad → first epoch]

"Community tier is free forever.

```bash
pip install adaad
adaad --dry-run   # nothing is modified
adaad --run       # first governed epoch
```

Or clone the repo and run python onboard.py — it handles everything in under 60 seconds."

---

### CALL TO ACTION (10:00–end)

"Link in the description. Star the repo if this was useful. I'll be posting more about the architecture — subscribe if you want to see how the genetic algorithm and self-calibrating fitness weights work."

---

## Upload checklist

- [ ] Record demo
- [ ] Export at 1080p60
- [ ] Thumbnail: terminal PASS/HALT split
- [ ] Description: link to GitHub, PRICING.md, newsletter
- [ ] Tags: constitutional AI, autonomous coding, AI agents, open source, devtools, governance
- [ ] End screen: subscribe + link to governance deep-dive video
- [ ] Pinned comment: GitHub link + pip install command
