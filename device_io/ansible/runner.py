from pathlib import Path
import os
import sys
import ansible_runner

BASE_DIR = Path(__file__).parent.resolve()
PLAYBOOK = BASE_DIR / "playbooks" / "get_facts.yml"
INVENTORY = BASE_DIR / "inventory.yml"

# Ensure ansible-playbook from this venv is first on PATH
venv_bin = Path(sys.executable).parent
os.environ["PATH"] = str(venv_bin) + os.pathsep + os.environ.get("PATH", "")

# Optional: disable host key checking for quick tests
envvars = {
    "ANSIBLE_PYTHON_INTERPRETER": sys.executable,
    "ANSIBLE_HOST_KEY_CHECKING": "False",
}

print("▶️  Running playbook via Ansible Runner...")

# Use cmdline `-i` to FORCE using the file as inventory (avoids treating it as a hostname)
r = ansible_runner.run(
    private_data_dir=str(BASE_DIR),   # working dir for runner artifacts
    playbook=str(PLAYBOOK),
    cmdline=f"-i {INVENTORY}",        # <- key fix: pass inventory via cmdline
    envvars=envvars,
)

print(f"\nStatus: {r.status}")
print(f"RC: {r.rc}")

# Iterate runner events (no events_callback attr; use r.events)
print("\n📋 Task results:")
for ev in r.events:
    if ev.get("event") in {"runner_on_ok", "runner_on_failed", "runner_on_unreachable"}:
        data = ev.get("event_data", {})
        host = data.get("host")
        task = data.get("task")
        state = ev["event"].replace("runner_on_", "")
        print(f"- {host}: {task} -> {state}")

if r.rc == 0:
    print("\n✅ Playbook completed successfully.")
else:
    print("\n❌ Playbook failed.")
