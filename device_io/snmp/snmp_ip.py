import subprocess
import re
from typing import Dict

def get(ip: str, community: str = "public") -> Dict[str, str]:
    """
    Zwraca mapę {IP: nazwa_interfejsu} z IP-MIB i IF-MIB.
    """
    # IP -> ifIndex
    out_ip = subprocess.run(
        ["snmpwalk", "-v2c", "-c", community, ip, "1.3.6.1.2.1.4.20.1.2"],
        capture_output=True, text=True
    ).stdout
    re_ip_idx = re.compile(r'\.(\d+\.\d+\.\d+\.\d+)\s*=\s*INTEGER:\s*(\d+)')
    ip_to_idx = {ip_str: int(idx) for ip_str, idx in re_ip_idx.findall(out_ip)}

    # ifIndex -> ifDescr
    out_descr = subprocess.run(
        ["snmpwalk", "-v2c", "-c", community, ip, "1.3.6.1.2.1.2.2.1.2"],
        capture_output=True, text=True
    ).stdout
    re_descr = re.compile(r'\.(\d+)\s*=\s*STRING:\s*"([^"]*)"')
    idx_to_name = {int(idx): name for idx, name in re_descr.findall(out_descr)}

    # wynik: IP -> nazwa interfejsu
    return {
        ip_addr: idx_to_name.get(if_idx, f"ifIndex {if_idx}")
        for ip_addr, if_idx in ip_to_idx.items()
    }

if __name__ == "__main__":
    device_ip = "192.168.92.131"
    community = "public"

    result = get(device_ip, community)
    print("IP -> Interface:")
    for ip_addr, iface in result.items():
        print(f"{ip_addr:15} -> {iface}")
