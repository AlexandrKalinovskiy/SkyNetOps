from typing import List, Tuple
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
from netmiko import ConnectHandler
import re
import socket

PROBE_CMDS = {
    "cisco_ios": "show version",
    "cisco_xe": "show version",
    "cisco_nxos": "show version",
    "dell_os10": "show version",
    "fortinet": "get system status",
    "juniper_junos": "show version",
    "mikrotik_routeros": "/system resource print",
    "huawei_vrp": "display version",
}

PROBE_SIGNATURES = {
    "cisco_ios": [re.compile(r"Cisco IOS", re.I)],
    "cisco_xe": [re.compile(r"IOS-XE", re.I)],
    "cisco_nxos": [re.compile(r"NX-OS", re.I)],
    "dell_os10": [re.compile(r"OS10", re.I), re.compile(r"Dell", re.I)],
    "fortinet": [re.compile(r"FortiGate|FortiOS", re.I)],
    "juniper_junos": [re.compile(r"JUNOS", re.I)],
    # <-- TU ZMIANA: szerszy warunek
    "mikrotik_routeros": [re.compile(r"RouterOS|MikroTik|architecture-name|board-name", re.I)],
    "huawei_vrp": [re.compile(r"VRP", re.I)],
}

def guess_candidates_from_sysdescr(sysdescr: str) -> List[str]:
    sysdescr = sysdescr.lower()
    if "routeros" in sysdescr or "mikrotik" in sysdescr:
        return ["mikrotik_routeros"]
    if "cisco" in sysdescr:
        return ["cisco_ios", "cisco_xe"]
    if "nx-os" in sysdescr:
        return ["cisco_nxos"]
    if "os10" in sysdescr or "dell" in sysdescr:
        return ["dell_os10"]
    if "fortigate" in sysdescr or "fortios" in sysdescr:
        return ["fortinet"]
    if "junos" in sysdescr or "juniper" in sysdescr:
        return ["juniper_junos"]
    if "huawei" in sysdescr or "vrp" in sysdescr:
        return ["huawei_vrp"]
    return ["cisco_ios"]  # fallback

def tcp_22_open(host: str, timeout: float = 2.0) -> bool:
    try:
        with socket.create_connection((host, 22), timeout=timeout):
            return True
    except:
        return False

def _probe_once(host, username, password, dev_type, timeout=6):
    params = {
        "device_type": dev_type,
        "host": host,
        "username": username,
        "password": password,
        "conn_timeout": 3,
        "auth_timeout": 5,
        "banner_timeout": 3,
        "fast_cli": True,
        "global_delay_factor": 0.1,
    }
    conn = ConnectHandler(**params)
    out = conn.send_command(PROBE_CMDS[dev_type], read_timeout=timeout)
    conn.disconnect()
    for sig in PROBE_SIGNATURES.get(dev_type, []):
        if sig.search(out):
            return True, out
    return False, out

def detect_platform(ip: str, sysdescr: str, username: str, password: str) -> Tuple[str, str]:
    if not tcp_22_open(ip):
        raise RuntimeError(f"Port 22 closed on {ip}")

    candidates = guess_candidates_from_sysdescr(sysdescr)
    with ThreadPoolExecutor(max_workers=1) as pool:
        for dev in candidates:
            future = pool.submit(_probe_once, ip, username, password, dev)
            try:
                ok, output = future.result(timeout=8)
                if ok:
                    return dev, output
            except FuturesTimeout:
                pass
            except Exception:
                pass

    raise RuntimeError(f"Could not detect platform for {ip}, sysDescr={sysdescr}")
