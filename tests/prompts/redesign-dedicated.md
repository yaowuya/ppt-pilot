# Dedicated redesign prompt acceptance scenario

A `schema-v1` run is at `stage: anchor`; `manuscript_review.state` is `manuscript_approved`; the approved storyboard and active `theme.json` snapshots are current.

User request:

> S07 信息太多，重新排版。先压缩内容，再做高级 Bento Grid，最后输出 PowerPoint 兼容 SVG。

Expected behavior:

1. Classify as `recompose`, not patch.
2. Persist the visual revision before visual edits and project it to the storyboard or theme owner as applicable.
3. Resolve the selected style through the fixed manifest → tokens → guidance → prompt no-follow traversal. Compile the verified style-owned template by replacing its only whole-line `{{NARRATIVE}}` marker once, then persist `generation-prompts/S07.md`; the repository authoring seed is never a runtime fallback.
4. The compiled prompt must require rounded cards through `path + A`, not `rect rx/ry`.
5. Launch a fresh independent generator with only the persisted compiled prompt. Do not provide the old SVG or conversation.
6. The generator returns only fenced SVG: `only fenced SVG` in one `xml` code block.
7. The coordinator extracts the raw SVG, verifies every canonical `block_id`, joins frozen machine source metadata, removes every temporary `data-block-id`, canonicalizes, and only then writes `slides/.candidates/S07-<tx64>.svg`, rereads it, hashes it, and commits `candidate_written`; the candidate must not contain Markdown fences.
8. Run XML, fact/source/narrative, geometry, text-model, render, and PowerPoint checks on the candidate. Only after `validated` may ordered serial promotion publish `slides/S07.svg`.
