# fields/snmp_if_mac.py
from typing import Dict
from device_io.snmp.snmp_io.collector import SnmpCache

def get(cache: SnmpCache) -> Dict[int, str]:
    return cache.ifPhysAddress
