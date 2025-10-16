class DeviceEnsureError(Exception):
    pass

class NetBoxCreateError(Exception):
    pass

import pynetbox
from device_io.ssh import connect_ssh, disable_paging, run_command, detect_device
from device_io.commands import get_command, SHOW_VERSION, SHOW_INTERFACES
from rich.console import Console
from netbox_utils.dcim.device import ensure_device_registered
from netbox_utils.dcim.interface import upsert_interface
from netbox_utils.utils import sha256_of, clear_ips
from parsers.ai_parser import parse_cli_to_model
from models import Facts, Interface
from device_io.utils import extract_interface_section
from netbox_utils.ipam.ip import get_or_create_ip
import re

console = Console()

def start(device_type: str, device_name: str, host: str):
    # Connecting to NetBox
    nb = pynetbox.api(
        "http://10.8.0.3:8000", token="1ce666a0d2b006213716c1372f4704a94256c21d"
    )

    # =============== Connecting to the device (Netmiko) ====================
    console.print(f"[bold]🔌 Connecting[/] to {host}")
    try:
        conn = connect_ssh(host, "admin", "Op2oyxq##", device_type)
    except Exception as e:
        console.print(f"[bold red]✖ SSH connect failed:[/] {e}")
        raise ConnectionError() from e

    # =========== Collect facts and create device in NetBox ==============
    try:
        device, created = ensure_device_registered(nb, device_name=device_name, facts={})

        if not device and not created:
            # Device not exist
            disable_paging(conn, device_type)
            cmds = get_command(SHOW_VERSION, device_type, default="show version")
            facts_cli = run_command(conn=conn, command=cmds)
            facts = parse_cli_to_model(facts_cli, Facts)
            device, created = ensure_device_registered(nb, device_name=device_name, facts=facts)

        if created:
            console.print(f"[green]✔ Created device[/] [yellow]{device.name}[/] in NetBox")
        else:
            console.print(f"[cyan]ℹ Device exist[/] [yellow]{device.name}[/]")
    except Exception as e:
        raise DeviceEnsureError(f"Failed to collect facts for '{device_name}': {e}") from e

    # =========== Create interfaces ==============
    try:
        # 1. Get all interfaces (CLI)
        cmds = get_command(SHOW_INTERFACES, device_type, default="show interfaces")
        # cmds = [cmd.format(interface="") for cmd in SHOW_INTERFACES[device_type]]
        interfaces_cli = run_command(conn=conn, command=cmds)

        # 2. Interfaces CLI -> dict
        interfaces = re.findall(r'^\s*interface\s+([\w\/\.\-]+)', interfaces_cli, flags=re.MULTILINE)

        for iface_name in interfaces:
            print(f"Check {iface_name}\n")
            # 3. Sprawdzam po kolei sumy kontrolne (hash) wszystkich interfejsów w przypadku różnic parsuję i aktualizuję.
            iface_cli = extract_interface_section(interfaces_cli, iface_name)
            iface, created, changed = upsert_interface(nb=nb, device_id=device.id, if_name=iface_name)

            if not iface:
                raise Exception("Coś poszło nie tak")

            new_hash = sha256_of(iface_cli)
            old_hash = (iface.custom_fields or {}).get("cli_hash")

            if new_hash != old_hash:
                iface_parsed: Interface = parse_cli_to_model(iface_cli, Interface)
                iface, created, changed = upsert_interface(nb=nb, device_id=device.id, if_name=iface_name, description=iface_parsed.description)

                # Oczyścić interfejś od "starych" IP
                clear_ips(nb, iface_parsed.ipv4, iface)

                is_ok: bool = True

                for ip in iface_parsed.ipv4:
                    try:
                        nb_ip = get_or_create_ip(nb, device, ip.address, ip.is_primary, iface)
                    except Exception as e:
                        is_ok = False
                        continue

                if is_ok:
                    # Hash interfejsu zapisuje wyłącznie wtedy, gdy wszystkie dane zostały pomyślnie zaktualizowane.
                    iface, created, changed = upsert_interface(nb, device.id, iface_name, description=iface_parsed.description, cli_hash=new_hash)

                    if changed:
                        print(f"Interface {iface.name} has changed")

    except Exception as e:
        raise DeviceEnsureError(f"Failed to collect facts for '{device_name}': {e}") from e

if __name__ == "__main__":
    # start("cisco_ios", "ROUTER_1", "172.28.0.11")
    start("cisco_ios", "SWITCH_DC", "SWITCH_DC")
    # start("dell_os10", "DELL_TEST", "172.28.0.14")
    # detect_device("85.202.58.98", "admin", "Op2oyxq##")
