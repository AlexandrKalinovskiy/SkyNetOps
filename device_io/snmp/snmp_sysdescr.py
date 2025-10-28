import subprocess

def get(ip: str, community: str = "public") -> str:
    """
    Zwraca opis urządzenia (sysDescr).
    OID: 1.3.6.1.2.1.1.1.0
    """
    oid = "1.3.6.1.2.1.1.1.0"
    cmd = ["snmpget", "-v2c", "-c", community, ip, oid]
    result = subprocess.run(cmd, capture_output=True, text=True)

    print(result.stdout)
    # Przykładowa linia:
    # iso.3.6.1.2.1.1.1.0 = STRING: "Cisco IOS Software..."
    for line in result.stdout.splitlines():
        if "STRING:" in line:
            return line.split("STRING:")[-1].strip().strip('"')

    return ""

if __name__ == "__main__":
    ip = "172.16.2.54"
    community = "public"
    descr = get(ip, community)
    print("sysDescr:", descr)
