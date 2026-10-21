---
modified: 2026-10-21T09:40:18+08:00
created: 2026-10-05T09:33:17+08:00
---
# Home

This is a local prototype, not approved team documentation. It is set up for the [LLM Wiki pattern](https://gist.githubusercontent.com/karpathy/442a6bf555914893e9891c11519de94f/raw/ac46de1ad27f92b28ac95459c782c07f6b8c964a/llm-wiki.md): an agent maintains linked Markdown pages, a content index, and an operations log as material is captured and reviewed. Open it as an Obsidian vault or follow the Markdown links on GitHub.

## Where do you want to start?

- **Work on something:** Open [Projects](Projects/_projects.md) to find the project, understand its purpose and context, and follow its links to the repository and issues where implementation work happens.
- **Explore a question:** Start with [Maps](Atlas/Maps/Maps.md) to follow a curated route through a subject, or [Resources](Atlas/Maps/Resources.md) for reusable references. Follow links into [Notes](Atlas/Notes/_notes.md) and project pages; a note can connect more than one project.
- **Capture something unfinished:** Put an idea, source link, or clipping in the [+ inbox](+/_inbox.md) with where it came from and why it may matter. It stays unreviewed until its provenance, sensitivity, and destination are checked with a human.

## How the pages fit together

This page is the starting point for the whole wiki. Pages beginning with `_`, such as [Projects](Projects/_projects.md) and [Notes](Atlas/Notes/_notes.md), are landing pages for their folders: they explain what belongs there and show what is available. The [inbox](+/_inbox.md) has a landing page too. Its Obsidian view is optional; the page and Markdown links still work on GitHub.

[Maps](Atlas/Maps/Maps.md) explains how to gather, develop, and navigate connections between pages. Maps are curated routes through a subject or responsibility, not required categories or folders. A landing page can also act as a map: *map* describes what a page helps you do, not which folder it is in. Follow links rather than expecting the folder tree to tell the whole story. For a page-by-page catalogue, including individual unreviewed clips, use the [wiki index](index.md); it is updated on each ingest. The [LLM operations log](log.md) records what the agent changed, not a history of team decisions. Indexing a clip makes it discoverable, not approved.

## Find your way back

- [People](Atlas/Maps/People.md) links the minimal profiles used by project pages.
- [Tags](Atlas/Maps/Tags.md) describes the draft tag guidance; map links remain the main routes through the wiki.
- [Projects](Projects/_projects.md) groups work by current intensity: on, ongoing, simmering, or sleeping. Sleeping includes cold or finished work; there is no separate archive.

## From capture to shared context

When material is ready for review, connect it to the relevant project or map, or make a durable note and link it from there. Attribute substantive claims to their sources and keep proposals distinct from agreed decisions. This is a local prototype, not approved team documentation; only a human can approve team decisions or standards. Project pages give context and may hold non-issue follow-ups, but GitHub issues own implementation task state.

## Check the vault

Obsidian Linter formats individual notes. After changing pages or paths, run `python3 .agents/skills/holotape-check/scripts/check_vault.py` at the vault root to check links, index coverage, project and clip conventions, and Bases folder references. The [vault-check skill](.agents/skills/holotape-check/SKILL.md) explains how agents use the command. It does not validate all YAML or replace checking views in Obsidian.

## License

Selected original wiki writing and templates are available under [CC BY 4.0](LICENSE.md). Imported material, project pages based on external sources, and attachments are excluded pending a rights and sensitivity review; see the [license scope](LICENSE.md).
