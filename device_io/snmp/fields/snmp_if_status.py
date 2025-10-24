# fields/snmp_if_status.py
from typing import Dict, TypedDict
from device_io.snmp.snmp_io.collector import SnmpCache

class IfStatus(TypedDict):
    admin: int  # 1=up,2=down,3=testing
    oper:  int  # 1=up,2=down,3=testing,4=unknown,5=dormant,6=notPresent,7=lowerLayerDown

def get(cache: SnmpCache) -> Dict[int, IfStatus]:
    out: Dict[int, IfStatus] = {}
    for idx in set(cache.ifAdminStatus) | set(cache.ifOperStatus):
        out[idx] = {
            "admin": cache.ifAdminStatus.get(idx, 0),
            "oper":  cache.ifOperStatus.get(idx, 0),
        }
    return out
