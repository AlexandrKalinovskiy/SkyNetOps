import re
import hashlib
from models import IPv4
from typing import List

def first(recordset):
    """Zwraca pierwszy element RecordSet albo None."""
    return next(iter(recordset), None)

def _slugify(s: str) -> str:
    s = s.strip().lower()
    s = re.sub(r"[^a-z0-9\-]+", "-", s)  # zamień nie-alfanum na '-'
    s = re.sub(r"-{2,}", "-", s).strip("-")  # zbij wielokrotne '-'
    return s or "model"

def iface_type_from_name(name: str) -> str:
    n = name.lower()
    if "25" in n:
        return "25gbase-x-sfp28"
    if "40" in n:
        return "40gbase-x-qsfpp"
    if "100" in n:
        return "100gbase-x-qsfp28"
    if n.startswith(("gi", "gigabitethernet")):
        return "1000base-t"
    if n.startswith(("te", "tengigabitethernet")):
        return "10gbase-x-sfpp"
    return "other"

def _norm_mac(mac: str) -> str:
    # 00:11:22:33:44:55 (lowercase, z dwukropkami)
    import re
    hexes = re.findall(r"[0-9A-Fa-f]{2}", mac)
    return ":".join(h.lower() for h in hexes[:6]) if hexes else mac

def sha256_of(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

def clear_ips(nb, ips: List[IPv4], iface):
    # Tutaj "usuwamy" IP których już nie ma na tym interfejście
    nb_ips = nb.ipam.ip_addresses.filter(assigned_object_id=iface.id)
    for np_ip in nb_ips:
        found = next((ip for ip in ips if ip.address == np_ip), None)
        if not found:
            np_ip.delete()

def is_management_interface(name: str, description: str = "") -> bool:
    text = f"{name} {description}".lower()

    # lista słów kluczowych, które wskazują na mgmt/oob
    mgmt_keywords = [
        "mgmt",
        "management",
        "oob",
        "out-of-band",
        "mng",
        "man",
        "fxp0",      # Juniper
        "me0",       # Juniper
        "em0",       # FreeBSD style
        "ilo",       # HP iLO
        "idrac",     # Dell iDRAC
        "ipmi",      # IPMI
    ]

    return any(keyword in text for keyword in mgmt_keywords)

def is_primary_interface(name: str, description: str = "") -> bool:
    text = f"{name} {description}".lower()

    # jeżeli trafi się mgmt/oob to od razu nie jest primary
    mgmt_keywords = ["mgmt", "management", "oob", "out-of-band", "idrac", "ipmi", "ilo"]
    if any(k in text for k in mgmt_keywords):
        return False

    primary_keywords = [
        "loopback", "lo",           # routing loopback
        "wan",                      # dostęp do internetu
        "core",                     # core network
        "transit",                  # połączenia między routerami
        "uplink",                   # połączenia w górę topologii
        "svi",                      # vlan layer-3
    ]

    # Proste wykrywanie popularnych typów primary
    if name.lower().startswith(("lo", "loopback")):
        return True

    if name.lower().startswith("vlan"):  # VLAN SVI
        return True

    if any(keyword in text for keyword in primary_keywords):
        return True

    return False