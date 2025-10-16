from typing import Dict

SHOW_VERSION: Dict[str, str] = {
    "cisco_ios": ["show version"],
    "dell_os10": ["show version"],
    "fortinet": ["get system status"],
}

SHOW_INTERFACES: Dict[str, str] = {
    "cisco_ios": ["show running-config | section interface",
                  "show interfaces | include ^[A-Za-z]|address is"],
    "dell_os10": ["show interfaces"],
    "fortinet": ["get system interface"],
}

# SHOW_INTERFACES: Dict[str, list[str]] = {
#     "cisco_ios": ["show running-config | section interface",
#                   "show interface {interface}"],
#     "dell_os10": ["show interfaces"],
#     "fortinet": ["get system interface"],
# }

class UnknownVendorError(Exception): ...

def get_command(
    commands_map: Dict[str, str],
    device_type: str | None,
    *,
    default: str | None = None,
    strict: bool = False,
) -> str:

    cmd = commands_map.get(device_type)
    if cmd:
        return cmd

    if strict:
        raise UnknownVendorError(f"Vendor '{device_type}' (normalized='{device_type}') is not supported.")
    if default:
        return default

    if commands_map is SHOW_VERSION:
        return "show version"
    if commands_map is SHOW_INTERFACES:
        return "show interfaces"
    
    # ostateczny fallback
    return "show version"