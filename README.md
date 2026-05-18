# worklog

An [agent skill](https://agentskills.io) that generates daily and weekly worklogs from Claude Code/Codex sessions and git commits.

## Install

```bash
npx skills add -g nohzafk/worklog-skill
```

The `-g` flag installs globally (`~/.claude/skills/`), which is required since worklogs are personal and span multiple projects.

## Usage

```
/worklog                  # daily worklog for today
/worklog 2026-05-10       # daily worklog for a specific date
/worklog week             # weekly summary for the current week
/worklog week 2026-W19    # weekly summary for a specific ISO week
```

> ⚠ The `week` keyword is required for weekly mode. `/worklog 2026-W19`
> (without `week`) will be interpreted as a daily date and fail.

## How It Works

1. Reads project list from `~/worklogs/config.yaml`
2. Extracts session data from Claude Code and Codex session logs
3. Gathers git commits for the target date(s)
4. Synthesizes a structured worklog and writes it to `~/worklogs/`

### Daily Output

- **Bottom Line** — 1-3 sentence summary leading with outcomes
- **Outcomes** — concrete results, tagged by project
- **Decisions & Rationale** — what was decided and why
- **Open Loops** — pending items with next steps
- **Raw Activity** — commits and session details (collapsed)

### Weekly Output

- **Trajectory** — narrative arc of the week
- **Key Outcomes** — ranked by impact, not chronology
- **Decisions Log** — table of decisions with rationale
- **Themes & Patterns** — honest observations
- **Open Loops Carried Forward** — flagged if stale
- **Week in Review** — daily breakdown (collapsed)

## Configuration

On first run, the skill creates `~/worklogs/config.yaml`:

```yaml
projects:
  - name: my-project
    path: /Users/me/projects/my-project
  - name: another-project
    path: /Users/me/projects/another-project
```

Edit this file to list the projects you want tracked.

## Requirements

- Python 3 (for session extraction)
- Git (for commit history)

## Inspiration

Inspired by [Francesco Di Lorenzo's worklog practice](https://x.com/frankdilo/status/2009565324061073656) — keeping a daily markdown worklog connected to Claude Code.

## License

MIT
