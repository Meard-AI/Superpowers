#!/usr/bin/env python3
"""
sandbox_enforcer.py — Invisible Attacks: Path Boundary Enforcer & Speculative Task Queue.

Three real capabilities:
  1. --path            validate a path mutation against an allowed root (advisory)
  2. --queue/--run-queue  enqueue speculative background tasks and actually run them
  3. --check-leak      report which spawned background processes are still alive

SCOPE HONESTY: --run-cmd scopes a child process's working directory and adds one
env var. That is NOT isolation — the child inherits the full environment, has the
same user, and can reach the whole filesystem. Real isolation requires an OS
sandbox (sandbox-exec, Landlock+seccomp, bubblewrap, or a container).

Path validation is advisory: it tells the CALLER whether a write is in bounds. It
cannot stop a write it is not asked about.
"""

import sys
import os
import json
import argparse
import subprocess
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional


def state_dir() -> Path:
    """Runtime state lives OUTSIDE the skill package, which is copied read-only."""
    override = os.environ.get("AGENT_SUPERPOWERS_STATE")
    if override:
        return Path(override).expanduser()
    base = os.environ.get("XDG_STATE_HOME")
    root = Path(base).expanduser() if base else Path.home() / ".local" / "state"
    return root / "agent-superpowers"


def queue_file() -> Path:
    return state_dir() / "speculative_queue.json"


def log_dir() -> Path:
    return state_dir() / "speculative_logs"


def load_queue() -> Dict[str, Any]:
    """Load the queue, discarding anything structurally malformed.

    The queue file is on disk and can be hand-edited or truncated mid-write, so
    every field is validated rather than trusted. A `tasks` value that is not a
    list of dicts must not reach the iteration code as an AttributeError.
    """
    default = {"next_id": 1, "tasks": []}
    qf = queue_file()
    if not qf.exists():
        return default
    try:
        with open(qf, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return default

    if isinstance(data, list):  # migrate the old bare-list format
        data = {"next_id": len(data) + 1, "tasks": data}
    if not isinstance(data, dict):
        return default

    raw_tasks = data.get("tasks")
    tasks = [t for t in raw_tasks if isinstance(t, dict)] if isinstance(raw_tasks, list) else []
    for t in tasks:
        t.setdefault("task_id", "spec-000")
        t.setdefault("command", "")
        t.setdefault("status", "QUEUED")
        # Normalize pid here so no downstream call has to guard int(pid).
        try:
            t["pid"] = int(t["pid"]) if t.get("pid") is not None else None
        except (TypeError, ValueError):
            t["pid"] = None

    try:
        next_id = int(data.get("next_id", len(tasks) + 1))
    except (TypeError, ValueError):
        next_id = len(tasks) + 1

    return {"next_id": max(1, next_id), "tasks": tasks}


@contextmanager
def queue_lock():
    """Serialize read-modify-write on the queue across processes.

    Without this, concurrent enqueues each read the old list and write back their
    own version, so most entries are silently lost. flock is POSIX-only; elsewhere
    this degrades to no locking, which is the prior behaviour.
    """
    try:
        qf = queue_file()
        qf.parent.mkdir(parents=True, exist_ok=True)
        handle = open(qf.with_name(qf.name + ".lock"), "w")
    except Exception:
        yield
        return
    try:
        try:
            import fcntl
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        except Exception:
            pass
        yield
    finally:
        try:
            import fcntl
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        except Exception:
            pass
        handle.close()


def save_queue(state: Dict[str, Any]) -> Optional[str]:
    """Write atomically so a crash mid-write cannot leave a truncated queue."""
    try:
        qf = queue_file()
        qf.parent.mkdir(parents=True, exist_ok=True)
        tmp = qf.with_name(qf.name + f".tmp.{os.getpid()}")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, qf)
        return None
    except Exception as e:
        return f"Failed to save speculative queue: {e}"


def is_within(child: str, parent: str) -> bool:
    try:
        Path(child).resolve().relative_to(Path(parent).resolve())
        return True
    except (ValueError, OSError):
        return False


def validate_path_boundary(path_str: str, allowed_root_str: Optional[str] = None,
                           action: str = "write") -> Dict[str, Any]:
    target_path = Path(path_str).expanduser().resolve()
    allowed_root = Path(allowed_root_str).expanduser().resolve() if allowed_root_str \
        else Path.cwd().resolve()

    allowed = is_within(str(target_path), str(allowed_root))
    return {
        "allowed": allowed,
        "target_path": str(target_path),
        "allowed_root": str(allowed_root),
        "action": action,
        "reason": (f"Path is within allowed root '{allowed_root}'" if allowed
                   else f"Path '{target_path}' violates allowed boundary root '{allowed_root}'"),
        "advisory": "Validation is advisory. It reports whether a mutation is in "
                    "bounds; it does not prevent one.",
    }


def process_alive(pid: int) -> bool:
    """Signal 0 probes liveness without delivering a signal."""
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True  # exists, owned by another user
    except Exception:
        return False


def run_queue(state: Dict[str, Any], allowed_root: str, dry_run: bool) -> Dict[str, Any]:
    """Actually execute QUEUED tasks in the background, recording real PIDs."""
    started, skipped = [], []
    logs = log_dir()
    if not dry_run:
        logs.mkdir(parents=True, exist_ok=True)

    for task in state["tasks"]:
        if task.get("status") != "QUEUED":
            skipped.append(task["task_id"])
            continue
        if dry_run:
            started.append({"task_id": task["task_id"], "command": task["command"], "pid": None})
            continue
        try:
            out_path = logs / f"{task['task_id']}.log"
            fh = open(out_path, "w", encoding="utf-8")
            env = os.environ.copy()
            env["SPECULATIVE_TASK_ID"] = task["task_id"]
            proc = subprocess.Popen(
                task["command"], shell=True,
                cwd=task.get("allowed_root") or allowed_root,
                stdout=fh, stderr=subprocess.STDOUT, env=env,
            )
            task["status"] = "RUNNING"
            task["pid"] = proc.pid
            task["log_file"] = str(out_path)
            started.append({"task_id": task["task_id"], "command": task["command"], "pid": proc.pid})
        except Exception as e:
            task["status"] = "FAILED"
            task["error"] = str(e)
            skipped.append(task["task_id"])

    return {"started": started, "skipped": skipped}


def refresh_statuses(state: Dict[str, Any]) -> None:
    """Reconcile RUNNING tasks against real process liveness."""
    for task in state["tasks"]:
        pid = task.get("pid")
        if task.get("status") == "RUNNING" and isinstance(pid, int):
            if not process_alive(pid):
                task["status"] = "FINISHED"


def main():
    parser = argparse.ArgumentParser(description="Invisible Attacks Path Boundary Enforcer & Speculative Queue")
    parser.add_argument("--path", type=str, help="Target file or directory path to validate for mutation")
    parser.add_argument("--allowed-root", "--target-dir", dest="allowed_root", type=str,
                        help="Allowed root directory boundary")
    parser.add_argument("--action", type=str, choices=["read", "write", "delete"], default="write",
                        help="Action type being performed")
    parser.add_argument("--run-cmd", "--isolate-cmd", dest="run_cmd", type=str,
                        help="Run a command with cwd scoped to the allowed root (NOT isolation)")
    parser.add_argument("--timeout", type=int, default=30, help="Timeout for --run-cmd (default: 30s)")
    parser.add_argument("--check-leak", action="store_true",
                        help="Report spawned background tasks that are still running")
    parser.add_argument("--queue-speculative", type=str, help="Enqueue a background speculative task")
    parser.add_argument("--run-queue", action="store_true", help="Execute all QUEUED speculative tasks")
    parser.add_argument("--clear-queue", action="store_true", help="Remove all tasks from the queue")
    parser.add_argument("--status", action="store_true", help="View speculative queue status")
    parser.add_argument("--json", action="store_true", help="Output machine-readable JSON format")
    parser.add_argument("--dry-run", action="store_true", help="Simulate without file/process side-effects")

    args = parser.parse_args()
    allowed_root = args.allowed_root or str(Path.cwd())

    # Mode 1: Path boundary validation
    if args.path:
        validation = validate_path_boundary(args.path, allowed_root, args.action)
        if args.json:
            print(json.dumps(validation, indent=2))
        else:
            print(f"[{'ALLOWED' if validation['allowed'] else 'DENIED'}] {validation['reason']}")
        sys.exit(0 if validation["allowed"] else 1)

    # Mode 2: Speculative queue
    if args.queue_speculative:
        with queue_lock():
            state = load_queue()
            task_id = f"spec-{state['next_id']:03d}"
            state["next_id"] += 1
            entry = {
                "task_id": task_id,
                "command": args.queue_speculative,
                "status": "QUEUED",
                "allowed_root": allowed_root,
                "pid": None,
            }
            state["tasks"].append(entry)
            res = {"status": "QUEUED", "task_id": task_id, "command": args.queue_speculative,
                   "queue_length": len(state["tasks"]), "dry_run": args.dry_run}
            if not args.dry_run:
                err = save_queue(state)
                if err:
                    res = {"status": "ERROR", "error": err}
        if args.json:
            print(json.dumps(res, indent=2))
        else:
            print(f"[{res['status']}] Speculative task {task_id}: '{args.queue_speculative}'")
        sys.exit(0 if res["status"] == "QUEUED" else 1)

    if args.run_queue:
        with queue_lock():
            state = load_queue()
            outcome = run_queue(state, allowed_root, args.dry_run)
            if not args.dry_run:
                save_queue(state)
        res = {"status": "SUCCESS", "started": outcome["started"],
               "started_count": len(outcome["started"]),
               "skipped_count": len(outcome["skipped"]), "dry_run": args.dry_run}
        if args.json:
            print(json.dumps(res, indent=2))
        else:
            print(f"[SUCCESS] Started {len(outcome['started'])} task(s), "
                  f"skipped {len(outcome['skipped'])}")
            for t in outcome["started"]:
                print(f"  {t['task_id']} pid={t['pid']}: {t['command']}")
        sys.exit(0)

    if args.clear_queue:
        res = {"status": "SUCCESS", "cleared": len(load_queue()["tasks"]), "dry_run": args.dry_run}
        if not args.dry_run:
            save_queue({"next_id": 1, "tasks": []})
        if args.json:
            print(json.dumps(res, indent=2))
        else:
            print(f"[SUCCESS] Cleared {res['cleared']} task(s)")
        sys.exit(0)

    if args.status:
        with queue_lock():
            state = load_queue()
            refresh_statuses(state)
            if not args.dry_run:
                save_queue(state)
        res = {"status": "OK", "queue_length": len(state["tasks"]),
               "queue_file": str(queue_file()), "speculative_queue": state["tasks"]}
        if args.json:
            print(json.dumps(res, indent=2))
        else:
            print(f"Speculative Execution Queue ({len(state['tasks'])} items) — {queue_file()}")
            for idx, q in enumerate(state["tasks"], 1):
                print(f"  {idx}. [{q['task_id']}] {q['status']} pid={q.get('pid')}: '{q['command']}'")
        sys.exit(0)

    # Mode 3: Scoped command execution (NOT isolation — see module docstring)
    if args.run_cmd:
        root = Path(allowed_root).expanduser()
        if not root.is_dir():
            err = {"status": "ERROR", "error": f"Allowed root '{allowed_root}' is not a directory"}
            print(json.dumps(err, indent=2) if args.json else f"[ERROR] {err['error']}",
                  file=None if args.json else sys.stderr)
            sys.exit(1)

        if args.dry_run:
            res = {"status": "SIMULATED", "command": args.run_cmd,
                   "allowed_root": str(root.resolve()), "dry_run": True}
            print(json.dumps(res, indent=2) if args.json
                  else f"[DRY-RUN] Would run '{args.run_cmd}' with cwd '{root}'")
            sys.exit(0)

        env = os.environ.copy()
        env["SANDBOX_SCOPED"] = "1"
        try:
            proc = subprocess.run(args.run_cmd, shell=True, cwd=str(root.resolve()),
                                  env=env, capture_output=True, text=True, timeout=args.timeout)
            res = {
                "status": "SUCCESS" if proc.returncode == 0 else "FAILED",
                "exit_code": proc.returncode, "command": args.run_cmd,
                "stdout": proc.stdout.strip(), "stderr": proc.stderr.strip(),
                "isolation": "none — cwd and one env var only; child inherits full environment",
            }
            if args.json:
                print(json.dumps(res, indent=2))
            else:
                print(f"[{res['status']}] Exit code {proc.returncode}")
                if proc.stdout:
                    print(proc.stdout, end="")
                if proc.stderr:
                    print(proc.stderr, file=sys.stderr, end="")
            sys.exit(proc.returncode)
        except subprocess.TimeoutExpired as e:
            res = {"status": "TIMEOUT", "error": f"Command exceeded {args.timeout}s",
                   "command": args.run_cmd,
                   "stdout": (e.stdout or b"").decode(errors="ignore") if isinstance(e.stdout, bytes)
                             else (e.stdout or ""),
                   "stderr": (e.stderr or b"").decode(errors="ignore") if isinstance(e.stderr, bytes)
                             else (e.stderr or "")}
            print(json.dumps(res, indent=2) if args.json else f"[TIMEOUT] {res['error']}",
                  file=None if args.json else sys.stderr)
            sys.exit(124)
        except Exception as e:
            res = {"status": "ERROR", "error": str(e), "command": args.run_cmd}
            print(json.dumps(res, indent=2) if args.json else f"[ERROR] {e}",
                  file=None if args.json else sys.stderr)
            sys.exit(1)

    # Mode 4: Real leak check — which spawned PIDs are still alive?
    if args.check_leak:
        state = load_queue()
        alive = []
        for task in state["tasks"]:
            pid = task.get("pid")
            if isinstance(pid, int) and process_alive(pid):
                alive.append({"task_id": task["task_id"], "pid": pid,
                              "command": task["command"], "status": task.get("status")})
        refresh_statuses(state)
        if not args.dry_run:
            save_queue(state)
        res = {
            "status": "LEAKS_DETECTED" if alive else "CLEAN",
            "leaks_detected": bool(alive),
            "live_processes": alive,
            "tracked_tasks": len(state["tasks"]),
            "queue_file": str(queue_file()),
            "scope_note": "Only processes THIS tool spawned are tracked. Processes "
                          "started by other means are not visible here.",
        }
        if args.json:
            print(json.dumps(res, indent=2))
        else:
            print(f"[{res['status']}] {len(alive)} live of {res['tracked_tasks']} tracked task(s)")
            for p in alive:
                print(f"  {p['task_id']} pid={p['pid']}: {p['command']}")
            print(f"Note: {res['scope_note']}")
        sys.exit(1 if alive else 0)

    parser.print_help()
    sys.exit(0)


if __name__ == "__main__":
    main()
