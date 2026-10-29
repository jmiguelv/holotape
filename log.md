---
up: "[[HOME]]"
related: []
aliases: []
author:
created: 2026-10-08
modified: 2026-10-08T18:06:00+08:00
tags: []
urls: []
---
# LLM operations log

Append a brief entry after an LLM operation changes the wiki. Record what changed and what still needs human review; do not paste sources, sensitive content, or a conversation transcript here. Earlier work and human edits have not been backfilled.

## [2026-10-08] maintain | establish the LLM wiki workflow

- Reframed the [agent guide](AGENTS.md) around source capture, reviewed integration, answering, and maintenance; added the [content index](index.md) and linked both entry points from [Home](HOME.md).
- Review: this workflow and the catalogue remain part of the local prototype; no team decisions or content have been approved by this entry.

## [2026-10-08] maintain | add clipping workflow

- Added the [clip-to-obsidian skill](.agents/skills/holotape-clip/SKILL.md), linked it from the [agent guide](AGENTS.md) and [index](index.md), and documented its `type/clip` tag in the [tag guide](Atlas/Maps/Tags.md).
- Review: the clipping workflow and tag remain proposed guidance; no source was imported or approved.

## [2026-10-09] clip | Unsloth decision-model guide

- Captured an attributed, link-only [clip](+/Train%20your%20own%20Decision%20Model%20with%20Unsloth.md) with original summary in the inbox; no source text, code, or images copied.
- Review: verify source claims, reuse rights, relevance, and destination before integrating it into durable pages.

## [2026-10-09] maintain | align index with LLM Wiki pattern

- Documented the [LLM Wiki adaptation](HOME.md) in the [agent guide](AGENTS.md); updated the [index](index.md) and [clipping workflow](.agents/skills/holotape-clip/SKILL.md) to list individual unreviewed clips on ingest, including the existing [Unsloth clip](+/Train%20your%20own%20Decision%20Model%20with%20Unsloth.md).
- Review: the workflow remains a local prototype. Indexing a source does not approve its claims, rights, relevance, or destination.

## [2026-10-09] maintain | simplify maps navigation

- Added [Maps](Atlas/Maps/Maps.md) as the guide and map entry point; updated [Home](HOME.md), the [index](index.md), [agent guide](AGENTS.md), [notes landing page](Atlas/Notes/_notes.md), [metadata conventions](Atlas/Notes/Metadata%20conventions.md), and [tag guide](Atlas/Maps/Tags.md) to point to it instead of the empty `Maps/Areas.md` placeholder.
- Review at the time: `Areas.md` was retained as an inactive pointer because external inbound links had not been verified. It was later removed during the experimental restructure.

## [2026-10-09] maintain | adapt maps, project intensities, and inbox

- Updated [Home](HOME.md), the [agent guide](AGENTS.md), [index](index.md), [license scope](LICENSE.md), [project landing page](Projects/_projects.md), [project template](_assets/templates/tpl%20-%20Project.md), [metadata conventions](Atlas/Notes/Metadata%20conventions.md), [tag guide](Atlas/Maps/Tags.md), [notes landing page](Atlas/Notes/_notes.md), and project/notes/people views for the Atlas layout and four project intensities. Removed the empty Add placeholder from `Atlas/Maps/`.
- Adapted the cooling-off workflow from Ideaverse Lite 1.5's Add page into the [inbox](+/_inbox.md) and added an age column to its [view](+/_inbox.base). No personal-vault text or attachments were imported.
- Review: the intensity folders describe attention, not approved lifecycle state; existing project `status` and `priority` values were left unchanged. The guidance is still a prototype.

## [2026-10-09] maintain | add vault-wide checks

- Added the local [vault checker](.agents/skills/holotape-check/scripts/check_vault.py), its [tests](.agents/skills/holotape-check/tests/test_check_vault.py), and the [vault-check skill](.agents/skills/holotape-check/SKILL.md). Linked the check from [Home](HOME.md), [agent guide](AGENTS.md), and [index](index.md).
- Review: this is a prototype convention check, not a Markdown formatter or complete YAML/Obsidian runtime validator.

## [2026-10-09] maintain | bundle vault checker with its skill

- Moved the [checker](.agents/skills/holotape-check/scripts/check_vault.py) and its [tests](.agents/skills/holotape-check/tests/test_check_vault.py) under the [vault-check skill](.agents/skills/holotape-check/SKILL.md); updated [Home](HOME.md), the [agent guide](AGENTS.md), and the [index](index.md) with the new command path.
- Review: the skill still uses the same prototype checks and does not replace Obsidian Linter or runtime validation.

## [2026-10-29] maintain | preserve Notion task migration tooling

- Saved the reusable [export parser](scripts/notion_markdown.py), [migration CLI](scripts/notion_migrate.py), and offline [parser](scripts/tests/test_notion_migration.py) and [client](scripts/tests/test_notion_client.py) tests. Completed the remaining approved-scope Notion task imports and metadata-only cleanup, preserving task properties and explicit source actions. Private exports, credentials, and migration state were not added to this vault.
- Review: native comment threads are not included in Markdown exports. Credential-bearing download details were omitted; unresolved source dates, historical questions, and current ownership still need human confirmation. Migration does not approve source proposals or verify historical progress as current.
