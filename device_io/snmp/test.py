import subprocess

ip, community = "172.16.2.3", "public"

# 1) Ogólny opis systemu (Linux i urządzenia): sysDescr / sysObjectID
subprocess.run(["snmpget", "-v2c", "-c", community, ip, "1.3.6.1.2.1.1.1.0"])  # sysDescr.0
subprocess.run(["snmpget", "-v2c", "-c", community, ip, "1.3.6.1.2.1.1.2.0"])  # sysObjectID.0

# 2) Opisy/model z ENTITY-MIB (urządzenia sieciowe, jeśli wspierają)
subprocess.run(["snmpwalk", "-v2c", "-c", community, ip, "1.3.6.1.2.1.47.1.1.1.1.2"])  # entPhysicalDescr
subprocess.run(["snmpwalk", "-v2c", "-c", community, ip, "1.3.6.1.2.1.47.1.1.1.1.7"])  # entPhysicalName
subprocess.run(["snmpwalk", "-v2c", "-c", community, ip, "1.3.6.1.2.1.47.1.1.1.1.13"]) # entPhysicalModelName

# 3) Opisy urządzeń z HOST-RESOURCES-MIB (Linux/Net-SNMP, często pfSense)
subprocess.run(["snmpwalk", "-v2c", "-c", community, ip, "1.3.6.1.2.1.25.3.2.1.3"])   # hrDeviceDescr
