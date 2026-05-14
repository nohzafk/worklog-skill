#!/usr/bin/env python3
"""
Extract Claude Code and Codex session data for a given project and date.

Usage:
    python extract_sessions.py --project-path /path/to/project --date 2026-04-12
    python extract_sessions.py --project-path /path/to/project --date 2026-04-12 --format json
    python extract_sessions.py --project-path /path/to/project --date 2026-04-12 --agent claude
    python extract_sessions.py --project-path /path/to/project --date 2026-04-12 --agent codex

Output (text):
    One block per session, showing user messages and substantive assistant responses.
    Sessions are labeled [claude] or [codex] based on origin.

Output (json):
    { "sessionId": [{"ts": ..., "type": ..., "text": ..., "agent": ...}, ...] }
"""

import argparse
import datetime
import glob
import json
import os

NOISE_PREFIXES = (
    "<local-command",
    "<command-name>",
    "<system-reminder>",
    "<user-prompt-submit-hook>",
    "<environment_context>",
    "<permissions instructions>",
    "# AGENTS.md instructions",
)

MAX_TEXT = 600


def extract_claude_sessions(project_path, target_date):
    """Return dict of sessionId -> list of records from Claude Code sessions."""
    encoded = project_path.replace("/", "-")
    session_dir = os.path.join(os.path.expanduser("~"), ".claude", "projects", encoded)

    if not os.path.isdir(session_dir):
        return {}

    # Only top-level .jsonl files — skip subagent subdirectories
    jsonl_files = glob.glob(os.path.join(session_dir, "*.jsonl"))
    sessions = {}

    for filepath in sorted(jsonl_files):
        try:
            f = open(filepath, errors="replace")
        except OSError:
            continue
        with f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except Exception:
                    continue

                ts = rec.get("timestamp", "")
                if not ts.startswith(target_date):
                    continue

                sid = rec.get(
                    "sessionId",
                    os.path.basename(filepath).replace(".jsonl", ""),
                )
                rtype = rec.get("type")
                text = None

                if rtype == "user":
                    content = rec.get("message", {}).get("content", "")
                    if isinstance(content, str):
                        if any(content.startswith(p) for p in NOISE_PREFIXES):
                            continue
                        text = content[:MAX_TEXT].strip()
                    elif isinstance(content, list):
                        parts = [
                            i.get("text", "")
                            for i in content
                            if isinstance(i, dict) and i.get("type") == "text"
                        ]
                        joined = " ".join(parts).strip()
                        if joined and not any(joined.startswith(p) for p in NOISE_PREFIXES):
                            text = joined[:MAX_TEXT]

                elif rtype == "assistant":
                    msg_content = rec.get("message", {}).get("content", [])
                    if isinstance(msg_content, list):
                        parts = [
                            i.get("text", "")
                            for i in msg_content
                            if isinstance(i, dict)
                            and i.get("type") == "text"
                            and len(i.get("text", "")) > 80
                        ]
                        if parts:
                            text = parts[0][:MAX_TEXT]

                elif rtype == "last-prompt":
                    lp = rec.get("lastPrompt", "")
                    # Skip slash commands (e.g. "/git-commit") — not useful
                    if lp and not lp.startswith("/"):
                        text = f"[summary] {lp[:300]}"

                if text and text.strip():
                    sessions.setdefault(sid, []).append(
                        {
                            "ts": ts,
                            "type": rtype,
                            "text": text.strip(),
                            "agent": "claude",
                        }
                    )

    return sessions


def extract_codex_sessions(project_path, target_date):
    """Return dict of sessionId -> list of records from Codex sessions.

    Codex stores sessions under ~/.codex/sessions/YYYY/MM/DD/rollout-*.jsonl.
    Each file's first line is a session_meta record with payload.cwd, which
    determines the project the session belongs to. We scan the target date's
    directory plus the day before (to catch sessions that crossed midnight).
    """
    codex_root = os.path.join(os.path.expanduser("~"), ".codex", "sessions")
    if not os.path.isdir(codex_root):
        return {}

    try:
        target = datetime.date.fromisoformat(target_date)
    except ValueError:
        return {}

    # Look in day-of and day-before to catch sessions that crossed midnight
    candidate_dates = [target - datetime.timedelta(days=1), target]
    jsonl_files = []
    for d in candidate_dates:
        day_dir = os.path.join(
            codex_root, f"{d.year:04d}", f"{d.month:02d}", f"{d.day:02d}"
        )
        if os.path.isdir(day_dir):
            jsonl_files.extend(glob.glob(os.path.join(day_dir, "*.jsonl")))

    project_path = os.path.abspath(project_path)
    sessions = {}

    for filepath in sorted(jsonl_files):
        try:
            f = open(filepath, errors="replace")
        except OSError:
            continue
        with f:
            # First line should be session_meta with cwd
            first_line = f.readline().strip()
            if not first_line:
                continue
            try:
                meta = json.loads(first_line)
            except Exception:
                continue
            if meta.get("type") != "session_meta":
                continue
            meta_payload = meta.get("payload", {})
            session_cwd = meta_payload.get("cwd", "")
            if os.path.abspath(session_cwd) != project_path:
                continue

            sid = meta_payload.get("id") or os.path.basename(filepath).replace(
                ".jsonl", ""
            )

            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except Exception:
                    continue

                ts = rec.get("timestamp", "")
                if not ts.startswith(target_date):
                    continue

                rtype = rec.get("type")
                text = None
                norm_type = None

                if rtype == "event_msg":
                    payload = rec.get("payload", {})
                    if payload.get("type") == "user_message":
                        msg = payload.get("message", "")
                        if msg and not any(msg.startswith(p) for p in NOISE_PREFIXES):
                            text = msg[:MAX_TEXT].strip()
                            norm_type = "user"

                elif rtype == "response_item":
                    payload = rec.get("payload", {})
                    if payload.get("role") == "assistant":
                        content = payload.get("content", [])
                        if isinstance(content, list):
                            for c in content:
                                if (
                                    isinstance(c, dict)
                                    and c.get("type") in ("text", "output_text")
                                    and len(c.get("text", "")) > 80
                                ):
                                    text = c["text"][:MAX_TEXT].strip()
                                    norm_type = "assistant"
                                    break

                if text and norm_type:
                    sessions.setdefault(sid, []).append(
                        {
                            "ts": ts,
                            "type": norm_type,
                            "text": text,
                            "agent": "codex",
                        }
                    )

    return sessions


def format_text(sessions):
    """Render sessions in the human-readable text format."""
    if not sessions:
        print("(no sessions found)")
        return
    for sid in sorted(sessions, key=lambda s: sessions[s][0]["ts"]):
        records = sorted(sessions[sid], key=lambda r: r["ts"])
        start_ts = records[0]["ts"][11:16]
        end_ts = records[-1]["ts"][11:16]
        agent = records[0].get("agent", "claude")
        print(f"=== [{agent}] SESSION {sid[:8]}... ({start_ts}–{end_ts} UTC) ===")
        for r in records:
            print(f"[{r['type']}] {r['text']}")
        print()


def main():
    parser = argparse.ArgumentParser(
        description="Extract Claude/Codex session records for a project/date"
    )
    parser.add_argument(
        "--project-path", required=True, help="Absolute path to the project"
    )
    parser.add_argument(
        "--date", required=True, help="Target date in YYYY-MM-DD format"
    )
    parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format (default: text)",
    )
    parser.add_argument(
        "--agent",
        choices=["claude", "codex", "all"],
        default="all",
        help="Which agent's sessions to include (default: all)",
    )
    args = parser.parse_args()

    sessions = {}
    if args.agent in ("claude", "all"):
        sessions.update(extract_claude_sessions(args.project_path, args.date))
    if args.agent in ("codex", "all"):
        sessions.update(extract_codex_sessions(args.project_path, args.date))

    if args.format == "json":
        print(json.dumps(sessions, indent=2, ensure_ascii=False))
    else:
        format_text(sessions)


if __name__ == "__main__":
    main()
