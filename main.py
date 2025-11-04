from device_io.ansible.runner import run_playbook

def on_host_done(host: str, payload: dict) -> None:
    # 👉 Here you can push to NetBox, save to DB, emit to Kafka, etc.
    # For now, just print a compact per-host summary.
    stats = payload["stats"]
    print(
        f"🔔 DONE {host} | ok={stats['ok']} changed={stats['changed']} "
        f"failed={stats['failures']} unreachable={stats['unreachable']} skipped={stats['skipped']}"
    )
    # Optional: inspect first few tasks
    for t in payload["tasks"][:3]:
        print(f"   • {t['task']} -> {t['status']} (changed={t['changed']})")

if __name__ == "__main__":
    rc = run_playbook()
    raise SystemExit(rc)
