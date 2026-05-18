---
name: worklog
description: Generate daily or weekly worklogs from Claude/Codex sessions and git commits. Invoked as "/worklog" (today), "/worklog YYYY-MM-DD" (backfill a daily entry), "/worklog week" (current ISO week), or "/worklog week YYYY-Wnn" (specific ISO week).
argument-hint: "[YYYY-MM-DD | week [YYYY-Wnn]]"
---

Generate a worklog. The extraction script is at:
`~/.claude/skills/worklog/scripts/extract_sessions.py`

**Invocation arguments (as typed by the user):** `$ARGUMENTS`

## Step 1: Parse Arguments

Parse the `$ARGUMENTS` string above (it may be empty) to determine the mode:

- No arguments → MODE=daily, TARGET_DATE=today.
- One arg matching `YYYY-MM-DD` → MODE=daily, TARGET_DATE=that date (backfill).
- First arg is `week` or `weekly` → MODE=weekly.
  - No second arg → WEEK_LABEL derived from today.
  - Second arg matching `YYYY-Wnn` → WEEK_LABEL=that ISO week.
- Anything else → tell the user the expected syntax and stop.

## Step 2: Read Configuration

Read `~/worklogs/config.yaml`.

If it does not exist, create `~/worklogs/` and write:

```yaml
# Tracked projects for /worklog
projects:
  - name: my-project
    path: /Users/me/projects/my-project
```

Tell the user to edit `~/worklogs/config.yaml` with their projects, then re-run. Stop here.

---

## Daily Mode (MODE=daily)

### Step 3d: Determine Dates

```bash
python3 -c "
from datetime import date, timedelta
import sys
arg = sys.argv[1] if len(sys.argv) > 1 else None
d = date.fromisoformat(arg) if arg else date.today()
print(d.isoformat())
print(d.strftime('%A, %B %-d, %Y'))
print((d + timedelta(days=1)).isoformat())
" <TARGET_DATE_OR_EMPTY>
```

Line 1 = TARGET_DATE, line 2 = DATE_DISPLAY, line 3 = NEXT_DAY.

### Step 4d: Extract Session Data

For each project in config.yaml, run:

```bash
python3 ~/.claude/skills/worklog/scripts/extract_sessions.py \
  --project-path <path> \
  --date <TARGET_DATE>
```

Collect all output per project.

### Step 5d: Gather Git Commits

For each project:

```bash
git -C <path> log \
  --since="<TARGET_DATE>T00:00:00" \
  --until="<NEXT_DAY>T00:00:00" \
  --format="%h %s" \
  --no-merges 2>/dev/null
```

### Step 6d: Synthesize Daily Report

Analyze all session extracts and git commits. Write in this format:

```markdown
# <DATE_DISPLAY>

## Bottom Line

<1-3 sentences. Lead with outcomes — the "so what". If nothing happened: "Light day — no tracked activity.">

## Outcomes

<Concrete results. Past tense. Prefix every bullet [project-name].>

- **[project] What shipped or unblocked** — detail if needed.

## Decisions & Rationale

<Only if meaningful decisions were made. Skip section entirely if not.>

- **[project] What was decided** — why, what was rejected.

## Open Loops

<Only if genuinely pending items exist. Skip if not.>

- [project] What's in progress. Next concrete step.

## Raw Activity

<details>
<summary>Commits and session details</summary>

### Git Commits

**[project]:**
- abc1234 message

### Session Summaries

- **[project] session (HH:MM-HH:MM UTC):** One sentence on what the session was about.

</details>
```

**Rules:**
- Lead with the answer. Bottom Line stands alone.
- Outcomes over activities: "Rewrote config format" not "Edited config.el".
- Decisions capture WHY — include what was rejected when you can tell.
- Omit empty sections (no header if no content).
- Every bullet gets a `[project]` tag.

### Step 7d: Write File

Write to `~/worklogs/<TARGET_DATE>.md`.

If the file already exists, ask: overwrite or append an `## Update — HH:MM` section?

### Step 8d: Confirm

Print the file path and the Bottom Line as a preview.

---

## Weekly Mode (MODE=weekly)

### Step 3w: Determine the Week

```bash
python3 -c "
from datetime import date, timedelta
import sys
arg = sys.argv[1] if len(sys.argv) > 1 else None
if arg:
    year, week = arg.split('-W')
    monday = date.fromisocalendar(int(year), int(week), 1)
else:
    today = date.today()
    monday = today - timedelta(days=today.weekday())
sunday = monday + timedelta(days=6)
iso_year, iso_week, _ = monday.isocalendar()
print(monday.isoformat())
print(sunday.isoformat())
print(f'{iso_year}-W{iso_week:02d}')
print(monday.strftime('%B %-d'))
print(sunday.strftime('%B %-d, %Y'))
" <WEEK_LABEL_OR_EMPTY>
```

Lines: MONDAY, SUNDAY, WEEK_LABEL, MONDAY_DISPLAY, SUNDAY_DISPLAY.

### Step 4w: Check Daily Worklogs

```bash
python3 -c "
from datetime import date, timedelta
import os
monday = date.fromisoformat('MONDAY')
for i in range(7):
    d = monday + timedelta(days=i)
    path = os.path.expanduser(f'~/worklogs/{d.isoformat()}.md')
    exists = os.path.exists(path)
    print(d.isoformat(), d.strftime('%A'), 'EXISTS' if exists else 'MISSING', path)
"
```

Read each existing daily worklog file.

### Step 5w: Fill Gaps from Raw Data

For any day marked MISSING, gather raw data using the extraction script and git log (same as daily Steps 4d-5d, but substituting that day's date).

Days with no data at all = "No activity."

### Step 6w: Synthesize Weekly Report

```markdown
# Week of <MONDAY_DISPLAY> – <SUNDAY_DISPLAY>

## Trajectory

<2-4 sentences: narrative arc of the week. NOT a summary of days — synthesis of direction and momentum. "What's the story of this week?">

## Key Outcomes

<3-7 items ranked by impact, not chronology. Skip filler — if fewer than 3 meaningful things happened, say so.>

1. **[project] Outcome** — Why it matters.
2. **[project] Outcome** — Context.

## Decisions Log

<Skip section if no meaningful decisions this week.>

| Decision | Rationale | Project |
|---|---|---|
| What was decided | Why — constraint or insight | [project] |

## Themes & Patterns

<Patterns across the week. Be honest: if 80% was yak-shaving, say so. Skip if the week was too thin.>

- **Theme**: Observation.

## Open Loops Carried Forward

<Pending items at end of week. Add warning if open 2+ weeks. Skip if nothing meaningful pending.>

- [project] What's pending. Next step.

## Week in Review

<details>
<summary>Daily breakdown</summary>

### Monday, <date>
<2-3 bullets or "No activity">

### Tuesday, <date>
...

### Wednesday, <date>
...

### Thursday, <date>
...

### Friday, <date>
...

### Saturday, <date>
...

### Sunday, <date>
...

</details>
```

**Rules:**
- Trajectory is synthesis, not summary. Ask: what's the story?
- Key Outcomes ranked by impact. #1 = single most important thing.
- Decisions Log compounds over time — be specific about rationale.
- Themes require honesty, not self-congratulation.
- Multi-week open loops get flagged.
- Weekly view stands on its own; detail goes in the collapse.

### Step 7w: Write File

Write to `~/worklogs/<WEEK_LABEL>-worklog-weekly.md`.

If file exists, ask: overwrite or update?

### Step 8w: Confirm

Print the file path and the Trajectory section as a preview.
