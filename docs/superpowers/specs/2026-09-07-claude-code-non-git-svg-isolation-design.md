# Claude Code Non-Git SVG Isolation Design

**Date:** 2026-09-07
**Status:** Revised after review; real-host acceptance pending

## Goal

Allow `ppt-start` to generate SVG pages through a fresh-context Claude Code worker when the presentation workspace is a plain non-Git directory or a Git repository with an unborn `HEAD`, without creating Git state, weakening the coordinator-owned publication model, or coupling the shared Skill to Claude-only frontmatter.

## Confirmed root cause

The current shared contract correctly says that Git is not a PPT Pilot requirement, but it describes only an abstract `spawn_isolated_text_task` capability. The Claude Code installation does not provide a concrete adapter for that capability. During the reported run, the coordinator mapped fresh conversation isolation to `isolation: worktree`; built-in worktree creation then attempted to resolve a Git base commit and failed against an unborn `HEAD`.

Conversation-context isolation and worktree isolation are separate concerns:

- an ordinary Claude Code subagent starts with fresh conversation context and does not require Git;
- `isolation: worktree` creates a separate VCS checkout and requires a resolvable Git base unless custom worktree hooks replace the built-in implementation;
- PPT Pilot needs fresh conversation context and no data-capable tools; it must not request worktree isolation merely to obtain those properties.

The existing host-capability tests are synthetic contract oracles. They trust declared booleans and therefore do not prove that a Claude-specific adapter exists or that a non-Git launch uses the correct host route.

## User decisions

- Use a dedicated Claude Code custom agent rather than instruction-only behavior.
- Preserve the shared `ppt-start` Skill for Claude Code, Codex, and DeepSeek Harness.
- Do not require `git init`, a local commit, another repository, a directory switch, or a worktree.
- Accept Claude Code's unavoidable preload of `CLAUDE.md` and parent-session git status as ambient host context; instruct the worker to ignore both for slide content. Do not claim byte-pure prompt-only isolation.
- Do not stage, commit, push, or publish repository changes as part of this fix.

## Architecture

### Shared orchestration contract

`skills/ppt-start/` remains the portable workflow owner. Its two-field frontmatter remains unchanged. It continues to describe one abstract page-generator capability, but the capability is refined to distinguish:

1. fresh conversation history;
2. application Prompt passed by value;
3. no agent-initiated workspace/filesystem, shell, network, Skill, or MCP data access, with explicitly documented ambient host preload handled separately;
4. text-only return with host attribution;
5. optional concurrency and durable lookup.

The literal `tools=none` requirement is replaced by **no data-capable tools**. This distinction is necessary because current Claude Code rejects a custom subagent whose effective tool set is empty. A host may expose a non-data control utility solely to make the agent launchable; that utility is not an input source, output sink, or correctness dependency.

The page-generation Prompt is the only PPT Pilot content payload passed from the coordinator. Claude Code nevertheless preloads `CLAUDE.md` and the parent session's git status into ordinary custom subagents. The accepted practical boundary treats both as ambient host context that the worker must ignore for slide facts, wording, and visual direction; this route does not claim byte-pure prompt-only isolation. Parent conversation history and workspace file contents are not passed by the coordinator, and the worker has no data-capable tools with which to fetch them.

### Claude Code adapter

Add a repository-owned custom-agent definition:

`hosts/claude-code/agents/ppt-svg-generator.md`

Its frontmatter and body must enforce these properties:

- stable agent name `ppt-svg-generator`;
- ordinary subagent execution with no worktree isolation declaration;
- only a harmless, non-data host-control tool such as `TodoWrite` in the tool allowlist;
- no Read, Write, Edit, Bash, Glob, Grep, Web, Skill, MCP, browser, or other data-bearing tool;
- no instruction to inspect the working directory;
- an explicit instruction to ignore preloaded `CLAUDE.md` and parent-session git status when choosing slide content;
- output exactly one `xml` fenced block containing the complete SVG and no commentary;
- all page content derives from the supplied task text.

The shared host-isolation reference maps Claude Code's abstract spawn operation to this agent. The coordinator must omit `isolation` for this route. If the available Agent schema requires `worktree` or `remote`, the Claude adapter is unavailable and generation fails closed; the coordinator must not substitute either value.

### Other hosts

Codex and DeepSeek continue using their existing native or remote prompt-isolation capability. They do not install or depend on the Claude custom agent. The shared capability matrix remains authoritative for concurrency, attribution, recovery, and ordered publication.

## Data flow

1. The coordinator completes the existing in-memory style, narrative, source, and prompt preflight.
2. Before durable prompt/transaction/candidate writes, it negotiates a host adapter.
3. On Claude Code, capability succeeds only when `ppt-svg-generator` is registered as an ordinary subagent and its packaged policy contains no data-capable tools.
4. The coordinator passes the complete generation Prompt by value as the agent task. It passes no prompt path, workspace/source content, parent conversation history, prior SVG, or presentation file; the separately documented ambient `CLAUDE.md`/git-status preload remains a host behavior the worker must ignore.
5. The worker returns text only.
6. The coordinator extracts exactly one `xml` fence, performs block/source enrichment, SVG validation, candidate hashing, transaction transitions, and ordered final promotion under the existing schema-v2 contract.
7. Missing concurrency or durable lookup still reduces effective dispatch width to one without changing the immutable batch inventory width.

No schema-v2 transaction, manifest, candidate, final SVG, or PowerPoint field changes are required. The existing optional run-level `visual_generation_blocker` gains one closed state/reason tuple for adapter failure.

## Capability and error rules

The Claude adapter is `generator_unavailable` when any of the following is true:

- the custom agent is not installed or not registered;
- ordinary non-worktree subagents are unavailable;
- the host requires a Git/worktree or remote-isolation base;
- the effective custom-agent policy exposes a data-capable tool;
- attribution cannot be retained;
- the page Prompt cannot be passed by value;
- the worker result cannot be returned as text;
- the caller requires byte-pure prompt-only isolation with no ambient `CLAUDE.md` or git-status context.

A missing adapter must produce one actionable, schema-valid `visual_generation_blocker` with `state/reason: generator_unavailable` and `resource: none`, then stop. It must not:

- run `git init`;
- create an empty or non-empty commit;
- run `git add` or `git push`;
- switch the session to another repository;
- request `isolation: worktree` or `isolation: remote` as a fallback;
- invoke a nested Claude/Codex/DeepSeek CLI;
- use the coordinator's current context as the SVG generator;
- start or retain periodic polling when no asynchronous capacity change can resolve the blocker.

Existing prompt/transaction zero-write rules and previous-final preservation remain unchanged.

## Installation and rollback

Extend `tools/update-hosts.ps1` only for the Claude Code branch:

- source agent: `hosts/claude-code/agents/ppt-svg-generator.md`;
- default user destination: `~/.claude/agents/ppt-svg-generator.md`;
- project destination when `-ProjectClaude` is selected: `.claude/agents/ppt-svg-generator.md`;
- optional `-ClaudeAgentsRoot` supports explicit installations and isolated tests;
- previous agent backup goes outside the live `agents/` scan root, under `agent-backups/`;
- copy verification compares exact bytes or a deterministic digest;
- a failed agent copy/verification restores the previous live agent and leaves the installed Skills unchanged;
- Codex and DeepSeek installation paths and payloads remain unchanged.

The installer must state that a running Claude Code session may need to be reopened before the newly registered agent is discoverable.

The fix may update the user's Claude Code installation after repository verification. It must not delete the `.git` directory previously created in the presentation workspace; that is a separate destructive cleanup decision owned by the user.

## Documentation

Update the active shared references so they no longer conflate fresh context with worktree isolation:

- `skills/ppt-start/SKILL.md`
- `skills/ppt-start/references/workflow.md`
- `skills/ppt-start/references/redesign-prompt.md`
- `skills/ppt-start/references/artifact-contract.md`
- `skills/ppt-start/references/adaptive-concurrency.md`
- a new host-isolation adapter reference under `skills/ppt-start/references/`

Update `README.md` and `docs/acceptance.md` to distinguish:

- portable abstract capability;
- packaged Claude Code adapter;
- static/package verification;
- real-host non-Git smoke evidence.

Manual installations that copy only `skills/ppt-start/` must be documented as insufficient for Claude Code fresh SVG isolation unless the custom agent is installed separately.

## Tests

### Agent package tests

Verify that the custom agent:

- has the exact stable name;
- does not request worktree isolation;
- exposes only the approved non-data control tool;
- excludes every filesystem, shell, network, Skill, MCP, and browser tool class;
- requires one XML-fenced SVG and no commentary.

### Host-routing contract tests

Add cases for:

- plain non-Git workspace selects ordinary Claude agent;
- Git repository with unborn `HEAD` selects the same ordinary agent;
- Git repository with a commit selects the same ordinary agent;
- adapter missing fails `generator_unavailable` with zero generation writes;
- host requiring worktree/remote fails closed rather than mutating Git;
- Git state never changes capability selection;
- no-data-tool policy is required;
- unavoidable `CLAUDE.md`/git-status ambient context is acknowledged and explicitly ignored while parent conversation history remains absent;
- adapter failure emits the closed run-level blocker with one run write and zero production writes;
- existing width-one degradation and ordered publication remain unchanged.

These tests must model the adapter explicitly instead of setting `native_fresh_isolation=true` without proving a route.

### Installer tests

Use temporary Claude Skill and Agent roots to prove:

- initial agent installation;
- exact source/destination equality;
- one backup outside `agents/` after a second installation;
- no backup pollution under live scan roots;
- rollback after agent-copy or verification failure;
- Codex installation does not receive the Claude agent;
- DeepSeek plugin content and marketplace entry remain unchanged.

### Real-host acceptance

Repository tests cannot invoke a nested Claude Code session. After installation, a newly opened Claude Code session must run a smoke case from a temporary non-Git directory and record:

- no `.git` directory before or after;
- selected adapter `ppt-svg-generator`;
- no worktree/remote isolation request;
- ambient `CLAUDE.md`/git-status context is recorded and a harmless non-Prompt canary is absent from the compiled Prompt and SVG;
- Prompt passed by value;
- SVG returned as text and written only by the coordinator;
- expected attribution/result state.

Until that evidence exists, documentation must label real-host Claude non-Git acceptance `PENDING`, not `PASS`.

## Non-goals

- Replacing the schema-v2 generation transaction protocol.
- Changing SVG source metadata or visible-source-ID rules.
- Modifying PowerPoint conversion or Office verification.
- Creating Git repositories or commits for presentation workspaces.
- Adding equivalent host-specific agents to Codex or DeepSeek.
- Automating nested Claude Code smoke tests from repository unit tests.

## Success criteria

The change is implementation-complete when:

1. the dedicated Claude agent is packaged and installed transactionally;
2. active Skill references explicitly select ordinary non-worktree execution on Claude Code;
3. no active fallback instructs Git initialization, commits, directory switching, worktrees, remote isolation, nested CLI use, or coordinator-context generation;
4. focused agent, routing, and installer tests pass;
5. the full frozen repository suite passes;
6. temporary-root installer verification proves the Claude agent and Skills match repository sources byte-for-byte; real user-profile deployment remains a separate action;
7. real-host acceptance remains honestly `PENDING` until exercised in a restarted non-Git Claude Code session.
