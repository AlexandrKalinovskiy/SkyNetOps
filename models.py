# models.py
from typing import List, Optional, Literal
from pydantic import BaseModel, Field, field_validator, constr
from typing import Annotated

IPv4Address = Annotated[
    str,
    Field(pattern=r"^((25[0-5]|2[0-4]\d|[01]?\d?\d)\.){3}(25[0-5]|2[0-4]\d|[01]?\d?\d)/(3[0-2]|[12]?\d)$")
]

class IPv4(BaseModel):
    address: IPv4Address
    is_primary: Optional[bool] = False
    # @field_validator("address")
    # @classmethod
    # def forbid_default_route(cls, v: str) -> str:
    #     if v == "0.0.0.0/0":
    #         raise ValueError("default route 0.0.0.0/0 is not allowed on interface")
    #     return v

class Interface(BaseModel):
    name: str
    is_enabled: Optional[bool] = Field(
        default=False,
        description=(
            "Administrative status from configuration only.\n"
            "- If the interface config contains 'shutdown' → false.\n"
            "- If it contains 'no shutdown' → true.\n"
            "- If neither appears → true by default.\n"
            "Do NOT use operational lines to decide this."
        ),
    )
    is_up: Optional[bool] = Field(
        default=False,
        description=(
            "Operational link state from 'show interface' status line, e.g. "
            "'<intf> is up, line protocol is up' → true; "
            "'is down' or 'line protocol is down' → false. "
            "Do NOT infer from 'shutdown'."
        ),
    )
    description: Optional[str] = Field(
        default="",
        description="Interface description text if present (line 'description ...')."
    )
    speed: Optional[int] = None
    mtu: Optional[int] = None
    mac_address: Optional[constr(pattern=r"^[0-9a-fA-F]{2}([:\.-][0-9a-fA-F]{2}){5}$")] = None # type: ignore
    vlan_access: Optional[int] = Field(default=None, description="Access VLAN if applicable")
    vlan_trunk: Optional[List[int]] = Field(default=None, description="Allowed VLANs on trunk")
    vlan_subinterface: Optional[List[int]] = Field(
        default=None,
        description=(
            "List of VLAN IDs used for routed 802.1Q subinterfaces (router-on-a-stick or L3 tagging).\n"
            "Use when interface carries L3 traffic tagged with one or more VLANs.\n\n"
            "Examples:\n"
            "- Cisco: interface Gi0/1.10 → vlan_subinterface = [10]\n"
            "- Dell OS10: 'vlan-id dot1q 10' → vlan_subinterface = [10]\n"
            "- Multiple VLAN tags on routed interface: 'vlan-id dot1q 10' + 'vlan-id dot1q 11' → vlan_subinterface = [10, 11]\n\n"
            "Rules:\n"
            "- Do NOT combine with vlan_access or vlan_trunk (those are for L2 switchports).\n"
            "- Applies only to L3 interfaces with IP configuration and dot1q tags.\n"
            "- Order does not matter.\n"
        )
    )
    ipv4: List[IPv4] = Field(default_factory=list),

# class Facts(BaseModel):
#     hostname: Optional[str] = Field(
#         default=None,
#         description=(
#             "The system hostname of the network device. Extract it from the CLI prompt "
#             "or configuration (e.g. 'show running-config', 'display current-configuration'). "
#             "Examples: 'R1', 'core-sw1', 'edge-router-ny', 'fw01'. "
#             "Do not return IP addresses, serial numbers, or login banners. "
#             "Return only the actual hostname without domain (no FQDN)."
#         )
#     )
#     vendor: Optional[str] = None
#     model: Optional[str] = None
#     serial_number: Optional[str] = None
#     os_version: Optional[str] = None
#     platform: str = Field(
#         description=(
#             "Netmiko device_type – the exact SSH platform identifier required by Netmiko "
#             "to establish an SSH connection to the device. Based on the input data of the device "
#             "(e.g. sysDescr, sysObjectID, or model name like 'C2960X', 'SG350X-48', 'N4032F', etc.), "
#             "return exactly ONE valid Netmiko device_type. "
#             "Examples: 'cisco_ios', 'cisco_xe', 'cisco_nxos', 'dell_os10', 'dell_force10', "
#             "'hp_comware', 'mikrotik_routeros', 'juniper_junos', 'fortinet', 'arista_eos'. "
#             "For small business Cisco models (e.g. SG350X-48, SF300, SG500), automatically detect "
#             "that these devices use classic IOS-like CLI and return 'cisco_ios'. "
#             "If the platform cannot be reliably detected, return 'unknown'."
#         ),
#         examples=["cisco_ios", "hp_comware", "mikrotik_routeros", "fortinet"]
#     )
#     device_role: Optional[str] = None
#     interfaces: Optional[List[Interface]] = Field(
#         default=None,
#         description=()
#     )
#
#     @field_validator("device_role", mode="before")
#     @classmethod
#     def _default_role(cls, v):
#         # Jeśli AI zwróci null/""/None → ustaw switch
#         if v is None or (isinstance(v, str) and not v.strip()):
#             return "switch"
#         return v

class Facts(BaseModel):
    hostname: str = Field(
        description=(
            "Device hostname (system name). Example: SW-CORE-1. "
            "Should be taken from CLI 'show running-config | include hostname' "
            "or SNMP sysName (1.3.6.1.2.1.1.5.0). MUST NOT be empty."
        )
    )

    vendor: Optional[str] = Field(
        description=(
            "Vendor/manufacturer name. Must be normalized to lowercase. "
            "Possible values: cisco, dell, juniper, mikrotik, huawei, fortinet, vyos, ubiquiti, aruba. "
            "Source: CLI 'show version' or SNMP sysDescr. If unknown, use None."
        )
    )

    model: Optional[str] = Field(
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
        description=(
            "Platform identifier for automation libraries like Netmiko/NAPALM. "
            "Example: cisco_ios, dell_os10, juniper_junos, mikrotik_routeros. "
            "Value determines SSH driver selection. Set None if unknown."
        )
    )

    device_role: Optional[str] = Field(
        description=(
            "Device role of this device. switch, router, server, firewall "
        )
    )

    os_version: Optional[str] = Field(
        description=(
            "Operating system version string from CLI or SNMP. Example: '15.2(7)E4', 'OS10.5.1.4'. "
            "Extract from 'show version', '/system resource print', or SNMP sysDescr. "
            "Set None if not detected."
        )
    )

    mgmt_ip: Optional[str] = Field(
        description=(
            "Primary management IP address used for SSH/SNMP access. "
            "Optional helper field – may come from inventory or autodetection. "
            "Example: '10.10.50.11'."
        )
    )

    interfaces: List[str] = Field(
        description=(
            "List of interface names detected on the device. MUST include ALL interfaces. "
            "Source: SNMP ifDescr or CLI 'show interfaces', '/interface print'. "
            "Example: ['GigabitEthernet1/0/1', 'GigabitEthernet1/0/2', 'Vlan10', 'Port-Channel1']"
        )
    )

class DetectPlatform(BaseModel):
    platform: str = Field(
        description=(
            "Platform identifier compatible with automation libraries such as Netmiko or NAPALM. "
            "Used to determine the correct driver for SSH/SNMP/API communication.\n\n"
            "Examples by vendor:\n"
            "• Cisco: cisco_ios, cisco_xe, cisco_xr, cisco_nxos\n"
            "• Dell: dell_os6, dell_os9, dell_os10\n"
            "• Juniper: juniper_junos\n"
            "• Fortinet: fortinet\n"
            "• Huawei: huawei, huawei_olt, huawei_smartax, huawei_smartaxmmi, huawei_vrp \n"
            "• MikroTik: mikrotik_routeros, mikrotik_switchos\n"
            "• Linux-based (servers, pfSense, OPNsense, FreeBSD): linux\n"
            "• Unknown vendor or unsupported system: unknown\n\n"
            "Rules:\n"
            "- Never return null.\n"
            "- If the operating system is FreeBSD or derived from it (e.g. pfSense, OPNsense), "
            "return 'linux'.\n"
            "- If the platform cannot be determined, return 'unknown'."
        )
    )

class DetectDeviceRole(BaseModel):
    role: Optional[str] = Field(
        description=(
            "Network device role classification based solely on SNMP-accessible fields: "
            "model, platform, and sysDescr.\n\n"

            "Valid role values: switch, router, firewall, server, wireless_controller, unknown.\n\n"

            "Classification rules:\n"
            "- If sysDescr or model contains 'switch', classify as switch.\n"
            "- If sysDescr or platform contains 'router', classify as router.\n"
            "- If sysDescr contains 'pfSense' → ALWAYS classify as router.\n"
            "- If sysDescr contains 'VyOS', classify as router unless explicitly identified as firewall.\n"
            "- If sysDescr or model indicates firewall functionality "
            "(e.g. 'Fortinet', 'FortiGate', 'ASA', 'PAN-', 'Checkpoint'), classify as firewall.\n"
            "- If sysDescr mentions server OS (e.g. Windows Server, VMware ESXi, generic Linux), classify as server.\n"
            "- If sysDescr or model indicates wireless controller "
            "(e.g. 'WLC', 'Wireless Controller'), classify as wireless_controller.\n\n"

            "Fallback behavior:\n"
            "- If platform belongs to a routing vendor and role not clearly detected → router.\n"
            "- If no classification match or insufficient data → unknown."
        )
    )


class DetectVendor(BaseModel):
    vendor: Optional[str] = Field(
        description=(
            "Network device vendor based on hostname, hardware description (sysDescr), "
            "MAC address OUI, sysObjectID (enterprise OID), or platform.\n"
            "Valid examples: Cisco, Dell, Juniper, MikroTik, Huawei, HP, Fortinet, Netgate.\n\n"

            "Classification hints:\n"
            "- Do NOT classify operating system names as vendors (e.g. pfSense, VyOS, FreeBSD, Linux are NOT vendors).\n"
            "- If sysDescr contains 'pfSense', vendor should typically be 'Netgate' "
            "or set to 'unknown' if hardware manufacturer cannot be determined.\n"
            "- If MAC OUI lookup indicates a known vendor, use that value.\n"
            "- If sysObjectID belongs to a registered vendor enterprise tree, use that vendor name.\n"
            "- If hostname includes vendor branding (e.g. 'R1-Cisco'), consider that a strong hint.\n\n"

            "If multiple signals conflict: prefer MAC OUI > sysObjectID > hostname > sysDescr keywords.\n"
            "If still unsure, set vendor to unknown."
        )
    )

class NapalmLike(BaseModel):
    facts: Facts
    interfaces: List[Interface]
