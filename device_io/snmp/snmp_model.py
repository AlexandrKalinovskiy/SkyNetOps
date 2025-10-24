import subprocess
import re

def get(ip: str, community: str = "public") -> str:
    """
    Zwraca model urządzenia (ENTITY-MIB::entPhysicalModelName).
    OID: 1.3.6.1.2.1.47.1.1.1.1.13
    """
    oid = "1.3.6.1.2.1.47.1.1.1.1.13"
    cmd = ["snmpwalk", "-v2c", "-c", community, ip, oid]
    result = subprocess.run(cmd, capture_output=True, text=True)

    pattern = re.compile(r'STRING:\s*"([^"]+)"')
    for line in result.stdout.splitlines():
        match = pattern.search(line)
        if match:
            return match.group(1).strip()

    return "unknown"


# === PRZYKŁADOWE UŻYCIE ===
if __name__ == "__main__":
    ip = "172.16.2.91"
    community = "public"
    model = get(ip, community)
    print("Model:", model)
