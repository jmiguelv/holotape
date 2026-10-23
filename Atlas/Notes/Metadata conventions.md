---
up: "[[../Maps/Resources|Resources]]"
related: []
aliases: []
author:
created: 2026-10-07
modified: 2026-10-23T11:30:56+08:00
tags: []
urls: []
---
# Metadata conventions (draft)

Proposed conventions for this local prototype, based on the owner's requested fields and the frontmatter pattern in their personal reference vault. These are **not approved team policy**.

- All content pages and templates: `up` (first property where there is a parent map or entry page), `aliases` (list), `author` (person reference when confirmed), `created` and `modified` (timestamps maintained by Obsidian; see below), `urls` (list of external URLs), `related` (list of relevant vault pages), and `tags` (list, empty unless a tag has a specific purpose). See the [draft tags guide](../Maps/Tags.md) for the current vocabulary; map links remain primary. Empty fields mean *unknown or not yet set*, not a verified absence. Do not infer authors or roles.
- Projects also have `priority` (1–5, project-level), `leads` (list of people, including for one lead), `team` (list of people), and a `status` property. The folder under `Projects/` expresses current intensity (`on`, `ongoing`, `simmering`, or `sleeping`), not lifecycle status. `priority` describes current relative urgency across projects: **1 is most urgent, 5 is least urgent**. Leave it empty if not yet assessed, and update it as priorities change.
- Project lifecycle `status` values: `proposed`, `planning`, `ready`, `active`, `complete`; use `paused` when work is on hold. `status` is separate from intensity: a sleeping project need not be complete, and an ongoing effort need not have an `active` status. This describes a project containing many GitHub issues, not the state of individual issues. Keep issue tasks and assignments in GitHub. The project page may hold lightweight follow-ups without an issue (who, what, agreed due date) and a dated record of developments; log completed follow-ups, but link to GitHub issues rather than copying their task state.
- People pages live in `Atlas/Notes/People/`, are named `@Name.md`, linked from [People](../Maps/People.md), and may have a confirmed professional `role`. No personal HR or private contact information.
- Obsidian properties can reference people and notes using quoted wikilinks, e.g. `leads: ["[[Atlas/Notes/People/@Person 1]]"]`, `related: ["[[Atlas/Maps/Maps]]"]`, or `up: "[[HOME]]"`. GitHub does not make these links clickable: retain relative Markdown links in the body for cross-page references and use maps as entry points. `up` replaces the former inline parent links; GitHub readers must use the maps or browser navigation to go back.
- Existing pages' `created` dates reflect local file creation dates; these do not establish when an idea or decision originated. Templates leave both `created` and `modified` empty so no template timestamps are copied into new pages. The locally enabled `frontmatter-modified-date` plugin is configured to fill `created` from the new file's creation time and `modified` from the edit time when it first processes an edit, then update `modified` on later edits. Check that both have been populated before relying on them; without the plugin they remain empty. The plugin may use a timestamp with time and timezone rather than a date alone. Exclude `_assets/templates` in the plugin's settings and reload the plugin after changing that setting; otherwise it can stamp a template's own file creation time into `created`, which is then copied to new pages. The plugin settings are local and ignored by Git, so configure them on other machines too.

Templates live in [`_assets/templates/`](../../_assets/templates/) and are named `tpl - X.md` to distinguish them from notes. Use `tpl - Base.md` for both inbox items and durable notes; set `up` for the destination and mark inbox items unreviewed. When making a new page, insert the relevant template, replace placeholders, and link it from the relevant map or project. Review provenance and sensitivity before moving an inbox item into durable content.
