# fields/snmp_if_speed.py
from typing import Dict
from device_io.snmp.snmp_io.collector import SnmpCache

def get(cache: SnmpCache) -> Dict[int, int]:
    """
    Zwraca ifHighSpeed w Mb/s. Dla portów bez ifHighSpeed możesz dodać fallback do ifSpeed (tu pomijamy).
    """
    return cache.ifHighSpeed
