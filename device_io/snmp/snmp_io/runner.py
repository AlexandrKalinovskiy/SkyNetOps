# snmp_io/runner.py
import subprocess
from typing import List

def _run(cmd: List[str]) -> str:
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(res.stderr.strip() or "snmp tool failed")
    return res.stdout

def _bulkwalk_cmd(host, community, oid, timeout, n0=True, r=64, allow_non_increasing=False):
    # net-snmp 5.9.x styl: -C n0 -C r<NUM> [-C c]
    app_opts = []
    if n0: app_opts += ["-C", "n0"]
    if r:  app_opts += ["-C", f"r{r}"]
    if allow_non_increasing: app_opts += ["-C", "c"]
    return [
        "snmpbulkwalk",
        "-On", "-m", "", "-M", "",
        "-v2c", "-c", community,
        "-t", str(timeout), "-r", "1",
        *app_opts,
        host, oid
    ]

def _walk_cmd(version, host, community, oid, timeout, allow_non_increasing=False):
    app_opts = []
    if allow_non_increasing: app_opts += ["-C", "c"]
    return [
        "snmpwalk",
        "-On", "-m", "", "-M", "",
        f"-v{version}", "-c", community,
        "-t", str(timeout), "-r", "1",
        *app_opts,
        host, oid
    ]

def snmpbulkwalk_adaptive(host: str, community: str, oid: str, timeout: int = 2) -> str:
    # próby GETBULK
    for r in (128, 64, 32):
        try:
            return _run(_bulkwalk_cmd(host, community, oid, timeout, n0=True, r=r, allow_non_increasing=False))
        except RuntimeError:
            pass
    # GETBULK z -C c
    for r in (64, 32, 16):
        try:
            return _run(_bulkwalk_cmd(host, community, oid, timeout, n0=True, r=r, allow_non_increasing=True))
        except RuntimeError:
            pass
    # zwykły walk v2c
    try:
        return _run(_walk_cmd("2c", host, community, oid, timeout, allow_non_increasing=True))
    except RuntimeError:
        # ostatnia deska: v1
        return _run(_walk_cmd("1", host, community, oid, timeout, allow_non_increasing=True))
