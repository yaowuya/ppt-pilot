# Guided Topic-Only Behavior Scenario

## Task

Create an 8-slide presentation about reducing onboarding time for a 200-person software company. The audience is the leadership team, the purpose is to choose the next-quarter improvement priority, and the final slides must be standalone SVG. No sources or brand guide are supplied. The mode is omitted; it defaults to `guided`.

Do not invent company metrics. Treat the request as topic-only input. Inspect the supplied request before asking anything, and do not ask again for the topic, audience, purpose, slide count, or delivery format. Ask at most one substantive question per turn, provide a recommendation without treating it as approval, and actually wait for an explicit answer.

## Expected artifacts and stages

- [ ] `run.json` defaults to `mode: guided` and records the current durable stage.
- [ ] `简报.md` states audience, purpose, desired action, 8-slide target, assumptions, and evidence policy.
- [ ] Any missing consequential brief decision is handled by one direct question; no downstream stage runs while that question is pending.
- [ ] Brief, outline, and anchor checkpoints each require explicit approval; a recommendation or narrated pause is not approval.
- [ ] `研究.md` distinguishes general evidence from company-specific unknowns.
- [ ] `来源.md` contains stable source IDs or explicitly records that no source was available.
- [ ] After brief approval, `大纲.md` uses assertion titles and pyramid logic.
- [ ] After outline approval, `故事板.md` contains every required slide field and source mapping.
- [ ] The completed five-file manuscript advances to independent review, not directly to visual design.
- [ ] No anchor or final SVG is created before `manuscript_approved`, and no downstream production begins before anchor approval.
