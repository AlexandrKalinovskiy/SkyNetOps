# English comments for learning
from pathlib import Path
from automation.runner import run_playbook, TaskResult, PlaybookRunResult

def on_task(tr: TaskResult):
    """Process each host/task event."""
    if tr.status == "ok" and tr.msg:
        print(f"[{tr.host}] hostname -> {tr.msg}")

def on_stats(stats: dict):
    """Process summary."""
    print(f"📊 SNMP hostname stats: {stats}")

def get_hostname() -> PlaybookRunResult:
    current_dir = Path(__file__).resolve().parent
    project_root = current_dir.parents[1]

    automation_dir = project_root / "automation"
    pb = automation_dir / "playbooks" / "snmp_get_hostname.yml"
    inv = automation_dir / "hosts.ini"

    return run_playbook(
        playbook_path=pb,
        inventory=inv,
        per_task=on_task,
        on_stats=on_stats,
    )

if __name__ == "__main__":
    result = get_hostname()
    print(f"\nRC={result.rc}")
