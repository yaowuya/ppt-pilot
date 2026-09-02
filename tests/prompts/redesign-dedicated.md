# Dedicated redesign prompt acceptance scenario

A `schema-v1` run is at `stage: anchor`; `manuscript_review.state` is `manuscript_approved`; the approved storyboard and active `theme.json` snapshots are current.

User request:

> S07 信息太多，重新排版。先压缩内容，再做高级 Bento Grid，最后输出 PowerPoint 兼容 SVG。

Expected behavior:

1. Classify as `recompose`, not patch.
2. Persist the visual revision before visual edits and project it to the storyboard or theme owner as applicable.
3. Directly compile and save `generation-prompts/S07.md` from the approved storyboard, active theme, applicable revision projection, SVG compatibility contract, and the canonical page-generation template.
4. The compiled prompt must require rounded cards through `path + A`, not `rect rx/ry`.
5. Launch a fresh independent generator with only the persisted compiled prompt. Do not provide the old SVG or conversation.
6. The generator returns only fenced SVG: `only fenced SVG` in one `xml` code block.
7. Extract the block and write raw SVG to `slides/S07.svg`; the saved file must not contain Markdown fences.
8. Run XML, fact/source/narrative, geometry, text-model, render, and PowerPoint checks before promotion.
