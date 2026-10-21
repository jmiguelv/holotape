---
up: "[[HOME]]"
related: []
aliases:
  - Projects
author:
created: 2026-10-05T09:33:17+08:00
modified: 2026-10-21T09:40:18+08:00
tags:
  - type/map
urls: []
---
# Projects

Come here to understand a project or ongoing umbrella effort. Each page brings together its purpose, relevant knowledge, dated developments, and links to the repository and issues where implementation work is tracked.

## Four intensities

Adapted from Ideaverse Lite 1.5's *The Four Intensities of Efforts* (local reference vault): folders indicate how much attention an effort needs now, not its lifecycle stage or approval status.

- `on/` — active focus and near-term work.
- `ongoing/` — continuing responsibility or umbrella effort without a fixed finish.
- `simmering/` — worth keeping in view, but not an immediate focus.
- `sleeping/` — cold, finished, or otherwise inactive work; no separate archive is needed.

Revisit the intensity as bandwidth changes. The page's `status` and `priority` properties describe lifecycle and relative urgency separately; don't infer or change them just from the folder. Before moving a page, check inbound links, particularly from external issues.

## Find your next step

1. Find the project below. Open its **Purpose and outcome** to see what it is for, then **Context and knowledge** and **Project log** for the background and what has happened.
2. Use **Where to act** to find the repository and issues. Checkboxes under **Open actions** are coordination follow-ups, not a live view of GitHub issues. Some existing pages contain imported, unverified Notion snapshots; check their source before acting on them.
3. If you learn something worth keeping beyond the immediate work, link it from the project to a reviewed note or relevant map. Keep the source with substantive claims and mark proposals as such.

## Add a project

If an effort needs its own entry page, start from the [project template](../_assets/templates/tpl%20-%20Project.md). Put it in the folder matching its current intensity; name the file `Project - Project name.md` and use `# Project - Project name` as its heading. Link it from a relevant map or parent project. See the [draft metadata conventions](../Atlas/Notes/Metadata%20conventions.md) for project status values and people links. Keep only non-issue coordination follow-ups in its open-actions list; track implementation work in GitHub issues.

The Obsidian view below lists project pages in all four intensity folders. It does not list their checkboxes.

![[_projects.base]]

On GitHub, [browse this folder](./) to see its files.

## Open tasks

Tasks across all projects, with no due date or due in the next two weeks.

```tasks
not done
(no due date) OR (due on or before in 14 days)
description regex does not match /^\s*\[Who\]/i
group by due
sort by due
```