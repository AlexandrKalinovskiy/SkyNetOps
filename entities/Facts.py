from typing import Optional
from pydantic import BaseModel, Field

class Facts(BaseModel):
    hostname: str = Field(...,
          description=(
              "Device hostname (system name). Example: SW-CORE-1. "
              "Should be taken from CLI 'show running-config | include hostname' "
              "or SNMP sysName (1.3.6.1.2.1.1.5.0). MUST NOT be empty."
          )
    )

    vendor: Optional[str] = Field(
        default=None,
        description=(
            "Vendor/manufacturer name. Must be normalized to lowercase. "
            "Possible values: cisco, dell, juniper, mikrotik, huawei, fortinet, vyos, ubiquiti, aruba. "
            "Source: CLI 'show version' or SNMP sysDescr. If unknown, use None."
        )
    )

    model: Optional[str] = Field(
        default=None,
        description=(
            "Exact hardware model. Example: 'WS-C2960X-48LPD-L', 'N4064F', 'CCR1036-8G-2S+'. "
            "Required for NetBox device_type mapping. If not found, set None."
        )
    )

    serial_number: Optional[str] = Field(
        default=None,
        description=(
            "Chassis serial number. Example: 'FOC1234X1YZ'. "
            "If multiple serials exist (stack or VLT), provide ONLY the main serial or chassis 1. "
            "If not available, set None."
        )
    )

    platform: Optional[str] = Field(
        default=None,
        description=(
            "Platform identifier for automation libraries like Netmiko/NAPALM. "
            "Example: cisco_ios, dell_os10, juniper_junos, mikrotik_routeros. "
            "Value determines SSH driver selection. Set None if unknown."
        )
    )

    device_role: Optional[str] = Field(
        default=None,
        description=(
            "Device role of this device. switch, router, server, firewall "
        )
    )