import subprocess
import re
from typing import Dict

def get(ip: str, community: str = "public") -> Dict[str, str]:
    """
    Zwraca słownik {MAC: interfejs}.
    - ifDescr          -> 1.3.6.1.2.1.2.2.1.2
    - ifPhysAddress    -> 1.3.6.1.2.1.2.2.1.6
    Regexy są „luźne” i nie zakładają konkretnego prefiksu (iso./MIB::).
    """
    # --- ifDescr: indeks -> nazwa interfejsu ---
    oid_descr = "1.3.6.1.2.1.2.2.1.2"
    descr_out = subprocess.run(
        ["snmpwalk", "-v2c", "-c", community, ip, oid_descr],
        capture_output=True, text=True
    ).stdout

    # np. 'iso.3.6.1.2.1.2.2.1.2.1002 = STRING: "GigabitEthernet1/0/1"'
    re_descr = re.compile(r'\.(\d+)\s*=\s*STRING:\s*"([^"]*)"')
    ifdescr = {int(idx): name for idx, name in re_descr.findall(descr_out)}

    # --- ifPhysAddress: indeks -> MAC ---
    oid_mac = "1.3.6.1.2.1.2.2.1.6"
    mac_out = subprocess.run(
        ["snmpwalk", "-v2c", "-c", community, ip, oid_mac],
        capture_output=True, text=True
    ).stdout

    # np. '...1.6.1002 = Hex-STRING: 40 A6 E8 FD F0 4B'
    re_mac = re.compile(r'\.(\d+)\s*=\s*Hex-STRING:\s*([0-9A-Fa-f ]+)')
    idx_mac_pairs = re_mac.findall(mac_out)

    mac_to_iface: Dict[str, str] = {}
    for idx_str, mac_hex in idx_mac_pairs:
        idx = int(idx_str)
        hex_bytes = mac_hex.strip().split()
        if not hex_bytes:
            continue
        mac = ":".join(hex_bytes).upper()
        iface = ifdescr.get(idx, f"ifIndex {idx}")
        mac_to_iface[mac] = iface

    return mac_to_iface


# === PRZYKŁAD UŻYCIA ===
if __name__ == "__main__":
    ip = "172.16.2.202"
    community = "public"
    mapping = get(ip, community)
    print("MAC → Interfejs:")
    for mac, iface in mapping.items():
        print(f"{mac:20} -> {iface}")
