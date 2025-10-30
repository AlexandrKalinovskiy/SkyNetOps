import subprocess
import re

def get(ip: str, community: str = "public") -> str:
    oid = "1.3.6.1.2.1.1.6.0"
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
    ip = "172.16.2.245"
    community = "public"
    location = get(ip, community)
    print("Location:", location)
