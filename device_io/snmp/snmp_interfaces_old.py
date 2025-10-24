import subprocess
import re
from typing import Dict, List

def _mask_to_prefix(mask: str) -> int:
    # Np. "255.255.255.0" -> 24
    parts = [int(x) for x in mask.split(".")]
    bits = "".join(f"{p:08b}" for p in parts)
    return bits.count("1")

def get(ip: str, community: str = "public") -> Dict[str, Dict[str, List[str]]]:
    """
    Zwraca słownik:
    {
      MAC: {
        "iface": nazwa,
        "description": opis,
        "ip": [lista_cidr]  # np. ["172.16.2.245/24", "40.0.0.1/32"]
      }
    }
    """

    # --- ifDescr: indeks -> nazwa interfejsu ---
    oid_descr = "1.3.6.1.2.1.2.2.1.2"
    descr_out = subprocess.run(
        ["snmpwalk", "-v2c", "-c", community, ip, oid_descr],
        capture_output=True, text=True
    ).stdout
    re_descr = re.compile(r'\.(\d+)\s*=\s*STRING:\s*"([^"]*)"')
    ifdescr = {int(idx): name for idx, name in re_descr.findall(descr_out)}

    # --- ifAlias: indeks -> description ---
    oid_alias = "1.3.6.1.2.1.31.1.1.1.18"
    alias_out = subprocess.run(
        ["snmpwalk", "-v2c", "-c", community, ip, oid_alias],
        capture_output=True, text=True
    ).stdout
    re_alias = re.compile(r'\.(\d+)\s*=\s*STRING:\s*"([^"]*)"')
    ifalias = {int(idx): desc for idx, desc in re_alias.findall(alias_out)}

    # --- IP -> ifIndex ---
    # Działa i dla "IP-MIB::ipAdEntIfIndex.172.16.2.245 = INTEGER: 1002"
    # i dla wersji numerycznej "1.3.6...4.20.1.2.172.16.2.245 = INTEGER: 1002"
    oid_ip_idx = "1.3.6.1.2.1.4.20.1.2"
    ip_idx_out = subprocess.run(
        ["snmpwalk", "-v2c", "-c", community, ip, oid_ip_idx],
        capture_output=True, text=True
    ).stdout
    re_ip_idx = re.compile(r'([0-9]{1,3}(?:\.[0-9]{1,3}){3})\s*=\s*INTEGER:\s*(\d+)')
    ip_index_pairs = [(ipaddr, int(idx)) for ipaddr, idx in re_ip_idx.findall(ip_idx_out)]

    # --- IP -> maska ---
    oid_ip_mask = "1.3.6.1.2.1.4.20.1.3"
    ip_mask_out = subprocess.run(
        ["snmpwalk", "-v2c", "-c", community, ip, oid_ip_mask],
        capture_output=True, text=True
    ).stdout
    # IP-MIB::ipAdEntNetMask.172.16.2.245 = IpAddress: 255.255.255.0
    re_ip_mask = re.compile(r'([0-9]{1,3}(?:\.[0-9]{1,3}){3})\s*=\s*IpAddress:\s*([0-9]{1,3}(?:\.[0-9]{1,3}){3})')
    ip_to_mask = {ipaddr: mask for ipaddr, mask in re_ip_mask.findall(ip_mask_out)}

    # --- indeks -> [CIDR, ...] ---
    index_to_cidrs: Dict[int, List[str]] = {}
    for ipaddr, idx in ip_index_pairs:
        mask = ip_to_mask.get(ipaddr)
        if mask:
            prefix = _mask_to_prefix(mask)
            cidr = f"{ipaddr}/{prefix}"
        else:
            # Gdy brak maski, zwróć sam adres (albo /32 – wybierz co wolisz)
            cidr = ipaddr  # lub f"{ipaddr}/32"
        index_to_cidrs.setdefault(idx, []).append(cidr)

    # --- ifPhysAddress: indeks -> MAC ---
    oid_mac = "1.3.6.1.2.1.2.2.1.6"
    mac_out = subprocess.run(
        ["snmpwalk", "-v2c", "-c", community, ip, oid_mac],
        capture_output=True, text=True
    ).stdout
    re_mac = re.compile(r'\.(\d+)\s*=\s*Hex-STRING:\s*([0-9A-Fa-f ]+)')
    idx_mac_pairs = re_mac.findall(mac_out)

    mac_to_data: Dict[str, Dict[str, List[str]]] = {}
    for idx_str, mac_hex in idx_mac_pairs:
        idx = int(idx_str)
        hex_bytes = mac_hex.strip().split()
        if not hex_bytes:
            continue
        mac = ":".join(hex_bytes).upper()
        iface = ifdescr.get(idx, f"ifIndex {idx}")
        desc = ifalias.get(idx, "")
        cidrs = index_to_cidrs.get(idx, [])

        mac_to_data[mac] = {
            "iface": iface,
            "description": desc,
            "ip": cidrs
        }

    return mac_to_data


# === TEST ===
if __name__ == "__main__":
    host = "172.16.2.245"
    community = "public"
    mapping = get(host, community)
    for mac, data in mapping.items():
        print(mac, data)
