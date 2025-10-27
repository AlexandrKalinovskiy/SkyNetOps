import subprocess
import re

def get(ip: str, community: str = "public") -> str:
    """
    Zwraca numer seryjny urządzenia (ENTITY-MIB::entPhysicalSerialNum).
    OID: 1.3.6.1.2.1.47.1.1.1.1.11
    """
    oid = "1.3.6.1.2.1.47.1.1.1.1.11"
    cmd = ["snmpwalk", "-v2c", "-c", community, ip, oid]
    result = subprocess.run(cmd, capture_output=True, text=True)

    pattern = re.compile(r'STRING:\s*"([^"]*)"')
    for line in result.stdout.splitlines():
        match = pattern.search(line)
        if match:
            value = match.group(1).strip()
            if value:  # pomiń puste ""
                return value
    return "unknown"

if __name__ == "__main__":
    ip = "172.16.2.201"
    community = "public"
    serial = get(ip, community)
    print("Serial number:", serial)
