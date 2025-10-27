import subprocess

def get(ip: str, community: str = "public") -> str:
    """
    # Returns the hostname (sysName) from the SNMP device.
    OID: 1.3.6.1.2.1.1.5.0
    """
    oid = "1.3.6.1.2.1.1.5.0"
    cmd = ["snmpget", "-v2c", "-c", community, ip, oid]
    result = subprocess.run(cmd, capture_output=True, text=True)

    for line in result.stdout.splitlines():
        if "STRING:" in line:
            return line.split("STRING:")[-1].strip().strip('"')
    return ""


# === PRZYKŁADOWE UŻYCIE ===
if __name__ == "__main__":
    ip = "172.16.2.85"
    community = "public"
    hostname = get(ip, community)
    print("Hostname:", hostname)
