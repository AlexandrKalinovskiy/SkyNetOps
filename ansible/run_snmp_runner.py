from pathlib import Path
import os, sys, shutil, subprocess
import ansible_runner

BASE_DIR = Path(__file__).parent
PLAYBOOK = BASE_DIR / "playbooks" / "hello.yml"

# dopnij venv/bin do PATH
venv_bin = Path(sys.executable).parent
os.environ["PATH"] = str(venv_bin) + os.pathsep + os.environ.get("PATH","")

# 🟢 najważniejsze: wymuś interpreter Pythona dla Ansible
envvars = {
    "PATH": os.environ["PATH"],
    "ANSIBLE_PYTHON_INTERPRETER": sys.executable,  # <-- Twój venv python
}

print("▶️  Running via Ansible Runner…")
print(f"🧪 sys.executable = {sys.executable}")
print(f"🧪 which(ansible-playbook) = {shutil.which('ansible-playbook')}")

r = ansible_runner.run(
    private_data_dir=str(BASE_DIR),
    playbook=str(PLAYBOOK),
    envvars=envvars,
)

print("\n✅ Finished")
print(f"Exit code: {r.rc}")
