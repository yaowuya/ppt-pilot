# PPT Pilot Visual Prompt Assembly Implementation Plan Index

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement these plans in order. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement deterministic file-backed visual prompt assembly and a selectable “嘉为年中总结风格” without changing the FY26 deck or adding a runtime dependency.

**Architecture:** The work is split into seven ordered plans. Plans 1–2 establish visual-brief fixtures and contract wiring. Plan 3 adds precedence-aware revision history and deterministic `patch`/`recompose` behavior. Plans 4–6 add style discovery, Canway tokens/guidance, and the synthetic Office-safe reference SVG. Plan 7 integrates documentation and runs a short local regression pass.

**Tech Stack:** Markdown Agent Skill contracts, JSON assets and fixtures, Office-safe SVG, Python `unittest` contract tests.

## Global Constraints

- Execute plans strictly in order: 1 → 2 → 3 → 4 → 5 → 6 → 7.
- Do not modify `ppt-output/fy26-h1-auto-ops-review/` or any FY26 SVG.
- Do not add Python/JavaScript runtime requirements, SDKs, hooks, background services, remote assets, or host-specific tool syntax to the shared Skill.
- Use synthetic fixture and reference content only.
- Validation is limited to fast local Python contract tests and static SVG checks.
- Do not run Claude Code/Codex live host acceptance, PowerPoint import, full browser review, or deck regeneration.
- The current directory is not a Git repository; do not initialize Git and do not include commit steps during execution.

---

## Ordered plan files

1. [Visual brief fixtures and contract tests](2026-08-20-ppt-pilot-visual-brief-fixtures.md)
2. [Visual brief contract wiring](2026-08-20-ppt-pilot-visual-brief-contract.md)
3. [Visual revision precedence and modes](2026-08-20-ppt-pilot-visual-revision-modes.md)
4. [Style registry and Canway tokens](2026-08-20-ppt-pilot-style-registry.md)
5. [Canway style guidance integration](2026-08-20-ppt-pilot-canway-style-guidance.md)
6. [Canway reference SVG](2026-08-20-ppt-pilot-canway-reference-svg.md)
7. [Documentation integration and fast regression](2026-08-20-ppt-pilot-visual-integration.md)

Each plan ends with an independently testable checkpoint. If a plan fails, stop before starting the next one.
