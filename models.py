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

class Facts(BaseModel):
    hostname: str
    vendor: Optional[Literal["Cisco", "Dell", "Huawei", "Fortigate", "Juniper", "Mikrotik"]] = None
    model: constr(pattern=r"^[\w\-\.]+$")  # type: ignore # litery/cyfry/kreski/kropki
    serial_number: Optional[str] = None
    os_version: Optional[str] = None
    dev_os: Optional[str] = None
    device_role: Optional[Literal["switch", "router", "server", "firewall"]] = None

    @field_validator("device_role", mode="before")
    @classmethod
    def _default_role(cls, v):
        # Jeśli AI zwróci null/""/None → ustaw switch
        if v is None or (isinstance(v, str) and not v.strip()):
            return "switch"
        return v

class NapalmLike(BaseModel):
    facts: Facts
    interfaces: List[Interface]
