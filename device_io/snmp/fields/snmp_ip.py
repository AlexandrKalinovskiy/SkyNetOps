# fields/snmp_ip_old.py
from typing import List, TypedDict
from device_io.snmp.snmp_io.collector import SnmpCache

class IpRow(TypedDict):
    ip: str
    mask: str
    ifIndex: int

def get(cache: SnmpCache) -> List[IpRow]:
    return [{"ip": ip, "mask": mask, "ifIndex": idx} for (ip, mask, idx) in cache.ip_rows]
