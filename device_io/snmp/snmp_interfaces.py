# snmp_interfaces.py
from typing import Dict, List, Tuple, TypedDict
from device_io.snmp.snmp_io.collector import collect
from device_io.snmp.fields import snmp_if_name, snmp_if_descr, snmp_if_mac, snmp_if_status, snmp_if_speed, snmp_ip, snmp_if_alias
from netbox_utils.utils import sha256_of

class Iface(TypedDict, total=False):
    ifIndex: int
    ifName: str
    ifDescr: str
    description: str
    mac: str
    adminStatus: int
    operStatus: int
    highSpeedMbps: int
    ips: List[Dict[str, str]]  # [{"ip":..., "mask":...}, ...]

def get(host) -> Tuple[List[Iface], str]:
    community = "public"
    cache = collect(host, community, timeout=1)
    names  = snmp_if_name.get(cache)
    descrs = snmp_if_descr.get(cache)
    macs   = snmp_if_mac.get(cache)
    aliases = snmp_if_alias.get(cache)
    stats  = snmp_if_status.get(cache)
    speeds = snmp_if_speed.get(cache)
    iprows = snmp_ip.get(cache)

    # ipy per ifIndex
    ip_by_idx: Dict[int, List[Dict[str, str]]] = {}
    for row in iprows:
        ip_by_idx.setdefault(row["ifIndex"], []).append({"ip": row["ip"], "mask": row["mask"]})

    all_indices = set(descrs) | set(names) | set(macs) | set(stats) | set(speeds) | set(ip_by_idx)

    out: List[Iface] = []
    hash_lines: List[str] = []  # will be joined into a single string for hashing

    for idx in sorted(all_indices):
        st = stats.get(idx, {"admin": 0, "oper": 0})
        ips_list = ip_by_idx.get(idx, [])

        # Sort IP entries deterministically by (ip, mask)
        ips_sorted = sorted(ips_list, key=lambda x: (x.get("ip", ""), x.get("mask", "")))
        # Build compact "ip/mask" CSV for hash line
        ips_csv = ",".join(f'{i.get("ip", "")}/{i.get("mask", "")}' for i in ips_sorted)

        out.append({
            "ifIndex": idx,
            "ifName": names.get(idx, ""),
            "ifDescr": descrs.get(idx, ""),
            "description": aliases.get(idx, "") or "",
            "mac": macs.get(idx, ""),
            "adminStatus": st["admin"],
            "operStatus": st["oper"],
            "highSpeedMbps": speeds.get(idx, 0),
            "ips": ip_by_idx.get(idx, []),
        })

        # Build deterministic line for hashing (avoid spaces)
        hash_lines.append(
            f'{idx}|{names.get(idx,"")}|{descrs.get(idx,"")}|{aliases.get(idx,"") or ""}|'
            f'{macs.get(idx,"")}|{st["admin"]}|{st["oper"]}|{speeds.get(idx,0)}|{ips_csv}'
        )

        # Join lines and compute SHA-256
        hash_input = "\n".join(hash_lines)
        hash_hex = sha256_of(hash_input)

    return out, hash_hex

if __name__ == "__main__":
    host = "172.16.2.245"
    interfaces = get(host)
    from pprint import pprint
    pprint(interfaces)  # albo json.dumps(...)
