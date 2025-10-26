# snmp_io/collector.py
import re
from dataclasses import dataclass
from typing import Dict, List, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed

from device_io.snmp.snmp_io.runner import snmpbulkwalk_adaptive

# OID-y (numeryczne, bez MIB-ów)
IF_TABLE_BASE   = "1.3.6.1.2.1.2.2.1"        # ifTable.*
IFX_TABLE_BASE  = "1.3.6.1.2.1.31.1.1.1"     # ifXTable.*
IP_ADDR_BASE    = "1.3.6.1.2.1.4.20.1"       # ipAdEnt.*

@dataclass
class SnmpCache:
    ifDescr: Dict[int, str]
    ifPhysAddress: Dict[int, str]
    ifAdminStatus: Dict[int, int]
    ifOperStatus: Dict[int, int]
    ifName: Dict[int, str]
    ifHCInOctets: Dict[int, int]
    ifHCOutOctets: Dict[int, int]
    ifHighSpeed: Dict[int, int]
    ifAlias: Dict[int, str]
    ip_rows: List[Tuple[str, str, int]]

def _parse_if_table(stdout: str) -> Dict[str, Dict[int, str | int]]:
    """
    Parsuje snmpwalk po 1.3.6.1.2.1.2.2.1 (ifTable.*).
    Obsługuje:
      - STRING: "GigabitEthernet1/0/1"  -> bez cudzysłowów
      - Hex-STRING: b0 7d 47 ...        -> b0:7d:47:...
      - STRING: b0:7d:47:...            -> już gotowy MAC
      - INTEGER: 1/2/...
    """
    import re
    cols = {
        "2": "ifDescr",
        "6": "ifPhysAddress",
        "7": "ifAdminStatus",
        "8": "ifOperStatus",
    }
    out: Dict[str, Dict[int, str | int]] = {v: {} for v in cols.values()}

    rx = re.compile(
        r"\.1\.3\.6\.1\.2\.1\.2\.2\.1\.(\d+)\.(\d+)\s=\s([^:]+):\s(.*)$"
    )

    def _strip_quotes(s: str) -> str:
        s = s.strip()
        if len(s) >= 2 and s[0] == '"' and s[-1] == '"':
            return s[1:-1]
        return s

    def _normalize_mac(val: str) -> str:
        """
        Przyjmuje:
          - 'b0 7d 47 f5 c7 31'
          - 'B0:7D:47:F5:C7:31'
          - 'b0:7d:47:f5:c7:31'
        Zwraca: 'b0:7d:47:f5:c7:31'
        """
        v = val.strip().lower()
        if " " in v and ":" not in v:
            # 'b0 7d 47 ...' -> kolki
            return ":".join(v.split())
        # już jest dwukropkami lub inny string
        return v

    for line in stdout.splitlines():
        m = rx.match(line.strip())
        if not m:
            continue
        col, idx, vtype, val = m.groups()
        if col not in cols:
            continue
        key = cols[col]
        idx = int(idx)

        if key == "ifPhysAddress":
            # Obsłuż różne formy
            if vtype.startswith("Hex-STRING"):
                out[key][idx] = _normalize_mac(val)
            elif vtype == "STRING":
                # może być "b0:7d:..." albo pusty string
                sval = _strip_quotes(val)
                out[key][idx] = _normalize_mac(sval) if sval else ""
            else:
                # bywa 'OCTET STRING' itd.
                sval = _strip_quotes(val)
                out[key][idx] = _normalize_mac(sval) if sval else ""
            continue

        if vtype == "STRING":
            out[key][idx] = _strip_quotes(val)
        elif vtype == "INTEGER":
            out[key][idx] = int(val.split()[0])
        else:
            # inne typy nas tu nie interesują
            pass

    return out

def _parse_ifx_table(stdout: str) -> Dict[str, Dict[int, str | int]]:
    cols = {
        "1":  "ifName",         # STRING
        "6":  "ifHCInOctets",   # Counter64
        "10": "ifHCOutOctets",  # Counter64
        "15": "ifHighSpeed",    # Gauge32 (Mb/s)
        "18": "ifAlias",        # STRING  <-- NOWE
    }
    out: Dict[str, Dict[int, str | int]] = {v: {} for v in cols.values()}

    rx = re.compile(r"\.1\.3\.6\.1\.2\.1\.31\.1\.1\.1\.(\d+)\.(\d+)\s=\s([^:]+):\s(.*)$")

    def _strip_quotes(s: str) -> str:
        s = s.strip()
        if len(s) >= 2 and s[0] == '"' and s[-1] == '"':
            return s[1:-1]
        return s

    for line in stdout.splitlines():
        m = rx.match(line.strip())
        if not m:
            continue
        col, idx, vtype, val = m.groups()
        if col not in cols:
            continue
        key = cols[col]
        idx = int(idx)
        vtype = vtype.strip()
        if vtype == "STRING":
            out[key][idx] = _strip_quotes(val)
        else:
            # Counter64/Gauge32 itp.
            tok = val.split()[0]
            out[key][idx] = int(tok) if tok.isdigit() else 0
    return out


def _parse_ip_addr_table(stdout_ifindex: str, stdout_mask: str) -> List[Tuple[str, str, int]]:
    """
    Parsuje dwie kolumny ipAdEnt: ifIndex i NetMask → zwraca listę (ip, mask, ifIndex).
    """
    rx_idx  = re.compile(r"\.1\.3\.6\.1\.2\.1\.4\.20\.1\.2\.([0-9\.]+)\s=\sINTEGER:\s(\d+)")
    rx_mask = re.compile(r"\.1\.3\.6\.1\.2\.1\.4\.20\.1\.3\.([0-9\.]+)\s=\sIpAddress:\s([0-9\.]+)")

    ip2idx: Dict[str, int] = {}
    ip2mask: Dict[str, str] = {}

    for line in stdout_ifindex.splitlines():
        m = rx_idx.match(line.strip())
        if m:
            ip, idx = m.groups()
            ip2idx[ip] = int(idx)

    for line in stdout_mask.splitlines():
        m = rx_mask.match(line.strip())
        if m:
            ip, mask = m.groups()
            ip2mask[ip] = mask

    rows: List[Tuple[str, str, int]] = []
    for ip, idx in ip2idx.items():
        rows.append((ip, ip2mask.get(ip, "0.0.0.0"), idx))
    return rows

def collect(host: str, community: str, timeout: int = 2) -> SnmpCache:
    # 3 równoległe bulkwalki
    jobs = {
        "if_table":   (IF_TABLE_BASE,),
        "ifx_table":  (IFX_TABLE_BASE,),
        "ip_idx":     (f"{IP_ADDR_BASE}.2",),
        "ip_mask":    (f"{IP_ADDR_BASE}.3",),
    }

    results: Dict[str, str] = {}
    with ThreadPoolExecutor(max_workers=3) as ex:
        fut_map = {
            ex.submit(snmpbulkwalk_adaptive, host, community, params[0], timeout): name
            for name, params in jobs.items()
        }
        for fut in as_completed(fut_map):
            name = fut_map[fut]
            results[name] = fut.result()

    if_cols = _parse_if_table(results["if_table"])
    ifx_cols = _parse_ifx_table(results["ifx_table"])
    ip_rows = _parse_ip_addr_table(results["ip_idx"], results["ip_mask"])

    # Fallback: jeśli kolumna MAC pusta, dociągnij ją osobno (też GETBULK)
    if not if_cols["ifPhysAddress"]:
        only_mac = snmpbulkwalk_adaptive(host, community, "1.3.6.1.2.1.2.2.1.6", timeout)
        mac_only = _parse_if_table(only_mac)
        if_cols["ifPhysAddress"] = mac_only.get("ifPhysAddress", {})

    return SnmpCache(
        ifDescr        = {k: str(v) for k, v in if_cols["ifDescr"].items()},
        ifPhysAddress  = {k: str(v) for k, v in if_cols["ifPhysAddress"].items()},
        ifAdminStatus  = {k: int(v)  for k, v in if_cols["ifAdminStatus"].items()},
        ifOperStatus   = {k: int(v)  for k, v  in if_cols["ifOperStatus"].items()},
        ifName         = {k: str(v)  for k, v  in ifx_cols.get("ifName", {}).items()},
        ifHCInOctets   = {k: int(v)  for k, v  in ifx_cols.get("ifHCInOctets", {}).items()},
        ifHCOutOctets  = {k: int(v)  for k, v  in ifx_cols.get("ifHCOutOctets", {}).items()},
        ifHighSpeed    = {k: int(v)  for k, v  in ifx_cols.get("ifHighSpeed", {}).items()},
        ifAlias        = {k: str(v)  for k, v in ifx_cols.get("ifAlias", {}).items()},
        ip_rows        = ip_rows,
    )
