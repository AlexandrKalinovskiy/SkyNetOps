# English comments as you prefer
from __future__ import annotations
from pathlib import Path
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional
import os, sys, shutil
import ansible_runner

# ------------ Lightweight result models ------------

@dataclass
class TaskResult:
    playbook: str
    play: Optional[str]
    task: str
    action: Optional[str]
    host: str
    status: str            # "ok" | "failed" | "skipped" | "unreachable"
    changed: bool = False
    msg: Optional[str] = None
    stdout: Optional[str] = None
    stderr: Optional[str] = None
    rc: Optional[int] = None
    res: Dict[str, Any] = field(default_factory=dict)  # raw module result

@dataclass
class PlaybookRunResult:
    playbook: str
    rc: int
    per_host: Dict[str, List[TaskResult]] = field(default_factory=dict)
    stats: Dict[str, Any] = field(default_factory=dict)

# ------------ Core runner ------------

BASE_DIR = Path(__file__).parent.resolve()

def _env_with_venv() -> Dict[str, str]:
    """Ensure venv bin is first in PATH and interpreter is fixed."""
    env = os.environ.copy()
    venv_bin = Path(sys.executable).parent
    env["PATH"] = str(venv_bin) + os.pathsep + env.get("PATH", "")
    env["ANSIBLE_PYTHON_INTERPRETER"] = sys.executable
    return env

def run_playbook(
    playbook_path: str | Path,
    inventory: str | Path,
    extravars: Optional[Dict[str, Any]] = None,
    per_task: Optional[Callable[[TaskResult], None]] = None,     # ← callback per host/task
    on_stats: Optional[Callable[[Dict[str, Any]], None]] = None, # ← callback on final stats
    quiet: bool = True,
) -> PlaybookRunResult:
    """Execute a playbook. Stream events to callbacks and return aggregated results."""
    playbook_path = str(Path(playbook_path).resolve())
    inventory = str(Path(inventory).resolve())
    env = _env_with_venv()

    # Ensure automation-playbook is reachable even when launched from IDE button
    if not shutil.which("ansible-playbook", path=env["PATH"]):
        raise RuntimeError(
            "automation-playbook not found in PATH. Install 'automation' in the active venv "
            "or adjust PATH/Interpreter in your IDE."
        )

    per_host: Dict[str, List[TaskResult]] = {}
    summary_stats: Dict[str, Any] = {}

    def on_event(event: Dict[str, Any]):
        name = event.get("event", "") or ""
        data = event.get("event_data", {}) or {}

        is_ok       = name == "runner_on_ok"
        is_failed   = name == "runner_on_failed"
        is_skipped  = name == "runner_on_skipped"
        is_unreach  = name == "runner_on_unreachable"

        if is_ok or is_failed or is_skipped or is_unreach:
            host   = data.get("host")
            task   = data.get("task") or data.get("task_name") or "unnamed-task"
            play   = data.get("play")
            pb     = data.get("playbook") or Path(playbook_path).name
            action = data.get("task_action")
            res    = data.get("res", {}) or {}

            tr = TaskResult(
                playbook=pb,
                play=play,
                task=task,
                action=action,
                host=host,
                status=("ok" if is_ok else "failed" if is_failed else "skipped" if is_skipped else "unreachable"),
                changed=bool(res.get("changed", False)),
                msg=(str(res.get("msg")).strip() if isinstance(res.get("msg"), str) else None),
                stdout=(str(res.get("stdout")).strip() if isinstance(res.get("stdout"), str) else None),
                stderr=(str(res.get("stderr")).strip() if isinstance(res.get("stderr"), str) else None),
                rc=(res.get("rc") if isinstance(res.get("rc"), int) else None),
                res=res,
            )

            # Aggregate for return value
            per_host.setdefault(host, []).append(tr)
            # Stream to user callback (process per host/task live)
            if per_task:
                per_task(tr)

        elif name == "playbook_on_stats":
            stats = data.get("stats", {}) or {}
            summary_stats.update(stats)
            if on_stats:
                on_stats(stats)

    r = ansible_runner.run(
        private_data_dir=str(BASE_DIR),
        playbook=playbook_path,
        inventory=inventory,
        extravars=extravars or {},
        envvars=env,
        event_handler=on_event,
        quiet=quiet,
    )

    return PlaybookRunResult(
        playbook=Path(playbook_path).name,
        rc=int(r.rc or 0),
        per_host=per_host,
        stats=summary_stats,
    )

# Optional CLI test
if __name__ == "__main__":
    pb = BASE_DIR / "playbooks" / "hello_world.yml"
    inv = BASE_DIR / "hosts.ini"

    def print_task(tr: TaskResult):
        # Minimal live log; adapt to JSON logging, NetBox, etc.
        line = f"[{tr.host}] {tr.task} -> {tr.status}"
        if tr.changed: line += " (changed)"
        if tr.msg:     line += f" | {tr.msg}"
        print(line)

    def print_stats(stats: Dict[str, Any]):
        print("📊 Final stats:", stats)

    res = run_playbook(pb, inv, per_task=print_task, on_stats=print_stats)
    print(f"\nRC={res.rc}")
