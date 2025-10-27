import subprocess
import re
import json

def _snmpget(ip, community, oid):
    cmd = ["snmpget", "-v2c", "-c", community, "-Oqv", ip, oid]
    p = subprocess.run(cmd, capture_output=True, text=True)
    out = p.stdout.strip()
    return out if p.returncode == 0 and out else None

def _snmpget_int(ip, community, oid):
    v = _snmpget(ip, community, oid)
    if v is None:
        return None
    try:
        return int(v)
    except ValueError:
        # czasem zwraca "INTEGER: 2" gdy -Oqv nie zadziałało na danym agencie
        m = re.search(r"(-?\d+)", v)
        return int(m.group(1)) if m else None

def _snmpwalk_first(ip, community, oid):
    # Weź pierwszą wartość z walk jako "model" (np. entPhysicalModelName)
    cmd = ["snmpwalk", "-v2c", "-c", community, "-Oqv", ip, oid]
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        return None
    for line in p.stdout.splitlines():
        val = line.strip().strip('"')
        if val:
            return val
    return None

def _vendor_from_sysobjectid(soid: str) -> str:
    # szukamy enterprise numeru po 1.3.6.1.4.1.<X>
    m = re.search(r"\.1\.3\.6\.1\.4\.1\.(\d+)", soid)
    if not m:
        return "unknown"
    ent = int(m.group(1))
    vendors = {
        9: "cisco",
        2636: "juniper",
        12356: "fortinet",
        14988: "mikrotik",
        25461: "paloalto",
        2620: "checkpoint",
        674: "dell",
        11: "hp",
        8072: "net-snmp",   # często serwery/nix
        41112: "ubiquiti",
    }
    return vendors.get(ent, f"enterprise-{ent}")

def get(ip: str, community: str = "public"):
    data = {}
    data["sysDescr"]       = _snmpget(ip, community, "1.3.6.1.2.1.1.1.0") or ""
    data["sysObjectID"]    = _snmpget(ip, community, "1.3.6.1.2.1.1.2.0") or ""
    data["sysServices"]    = _snmpget_int(ip, community, "1.3.6.1.2.1.1.7.0")
    data["ipForwarding"]   = _snmpget_int(ip, community, "1.3.6.1.2.1.4.1.0")  # 1 fwd, 2 not fwd
    data["ifNumber"]       = _snmpget_int(ip, community, "1.3.6.1.2.1.2.1.0")
    data["bridgeAddress"]  = _snmpget(ip, community, "1.3.6.1.2.1.17.1.1.0")  # może zwrócić MAC lub fail
    data["vlanAware"]      = _snmpget_int(ip, community, "1.3.6.1.2.1.17.7.1.1.1.0") is not None
    # ENTITY-MIB (model); różni vendorzy mogą mieć index ≠ 1, ale 1 to dobry start
    data["modelName"]      = _snmpget(ip, community, "1.3.6.1.2.1.47.1.1.1.1.13.1") or _snmpwalk_first(ip, community, "1.3.6.1.2.1.47.1.1.1.1.13")
    data["vendor"]         = _vendor_from_sysobjectid(data["sysObjectID"])

    # Heurystyki
    l3 = (data["sysServices"] is not None and (data["sysServices"] & 4) != 0) or (data["ipForwarding"] == 1)
    l2 = (data["sysServices"] is not None and (data["sysServices"] & 2) != 0) or (data["bridgeAddress"] is not None)
    vlan = data["vlanAware"]

    role = "unknown"
    reasons = []

    # firewall po vendorze
    if data["vendor"] in {"fortinet", "paloalto", "checkpoint"}:
        role = "firewall"
        reasons.append(f"vendor={data['vendor']} zwykle oznacza firewall")

    # jeśli nie firewallem już rozpoznanym:
    if role == "unknown":
        if l3 and not l2:
            role = "router"; reasons.append("sysServices/IP-Fwd sugeruje L3 routing bez L2 bridge")
        elif l3 and l2:
            # L3 switch lub router z funkcjami bridge (w praktyce często 'switch L3')
            if vlan or data["ifNumber"] and data["ifNumber"] > 16:
                role = "switch"; reasons.append("L2+L3 + VLAN/dużo portów → przełącznik L3")
            else:
                role = "router"; reasons.append("L2+L3, ale brak silnych sygnałów switch → router")
        elif l2:
            role = "switch"; reasons.append("BRIDGE/Q-BRIDGE sygnalizuje L2")
        else:
            role = "unknown"; reasons.append("brak czytelnych sygnałów L2/L3")

    result = {
        "ip": ip,
        "vendor": data["vendor"],
        "model": data["modelName"] or "",
        "sysObjectID": data["sysObjectID"],
        "sysDescr": data["sysDescr"],
        "sysServices": data["sysServices"],
        "ipForwarding": data["ipForwarding"],
        "bridgeAddress_present": data["bridgeAddress"] is not None,
        "vlanAware": vlan,
        "ifNumber": data["ifNumber"],
        # "role_guess": role,
        # "reasons": reasons,
    }

    return json.dumps(result, ensure_ascii=False)

if __name__ == "__main__":
    ip = "172.16.2.3"
    community = "public"
    descr = get(ip, community)
    print("sysDescr:", descr)