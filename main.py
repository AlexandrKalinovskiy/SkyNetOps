class DeviceEnsureError(Exception):
    pass

class NetBoxCreateError(Exception):
    pass

import pynetbox
from device_io.ssh import connect_ssh, disable_paging, run_command
from device_io.commands import get_command, SHOW_VERSION, SHOW_INTERFACES
from device_io.snmp import snmp_hostname, snmp_sysdescr, snmp_model, snmp_serial, snmp_interfaces_old, snmp_ip_old
from rich.console import Console
from netbox_utils.dcim.device import ensure_device_registered
from netbox_utils.dcim.interface import upsert_interface
from netbox_utils.utils import sha256_of, clear_ips, is_valid_ip
from parsers.ai_parser import parse_cli_to_model
from models import Facts, DetectPlatform, DetectDeviceRole, DetectVendor
from device_io.utils import extract_interface_section
from netbox_utils.ipam.ip import get_or_create_ip
from concurrent.futures import ThreadPoolExecutor, as_completed
from ipaddress import IPv4Address
import re

console = Console()

def start(host: str):
    # Connecting to NetBox
    nb = pynetbox.api(
        "http://10.8.0.1:8000", token="97c50a928fff461721ec0eeb826f6e54eac6826e"
    )

    console.print(f"[bold]🔌Check IP... [/] {host}")
    hostname = snmp_hostname.get(host)
    if not hostname:
        return

    print(hostname)

    # =============== Connecting to the device (Netmiko) ====================
    # console.print(f"[bold]🔌 Connecting[/] to {host}")
    # try:
    #     conn = connect_ssh(host, "admin", "Op2oyxq##", device_type)
    # except Exception as e:
    #     console.print(f"[bold red]✖ SSH connect failed:[/] {e}")
    #     raise ConnectionError() from e

    # =========== Collect facts and create device in NetBox ==============
    try:
        device, created = ensure_device_registered(nb, device_name=hostname, facts={})

        if not device and not created:
            # Device not exist
            sys_descr = snmp_sysdescr.get(host)
            model = snmp_model.get(host)
            serial = snmp_serial.get(host)
            platform_detect = parse_cli_to_model(sys_descr, DetectPlatform)
            role_detect = parse_cli_to_model(sys_descr, DetectDeviceRole)
            vendor_detect = parse_cli_to_model(sys_descr, DetectVendor)
            print(platform_detect)
            facts = Facts(
                hostname=hostname,
                vendor=vendor_detect.vendor,
                model=model,
                serial_number=serial or "none",
                platform=platform_detect.platform,
                device_role=role_detect.role,
                os_version="unknown",
                mgmt_ip="",
                interfaces=[]
            )
            device, created = ensure_device_registered(nb, device_name=hostname, facts=facts)

        if created:
            console.print(f"[green]✔ Created device[/] [yellow]{device.name}[/] in NetBox")
        else:
            console.print(f"[cyan]ℹ Device exist[/] [yellow]{device.name}[/]")
    except Exception as e:
        raise DeviceEnsureError(f"Failed to collect facts for '{hostname}': {e}") from e

    # =========== Create interfaces ==============
    try:
        interfaces = snmp_interfaces.get(host)
        for mac, info in interfaces.items():
            iface = info.get("iface", "unknown")
            desc = info.get("description", "")
            ip_adresses = info.get("ip", [])

            print(f"{iface} : {mac}\n")

            iface, created, changed = upsert_interface(nb=nb, device_id=device.id, if_name=iface, mac_address=mac, description=desc)

            for ip in ip_adresses:
                print(f"{ip:15}")
                if created or changed:
                    if is_valid_ip(ip):
                        print(f"Set IP: {ip}")
                        nb_ip = get_or_create_ip(nb, device, ip, True, iface)

            # if not iface:
            #     raise Exception("Coś poszło nie tak")

            # new_hash = sha256_of(iface_cli)
            # old_hash = (iface.custom_fields or {}).get("cli_hash")
            #
            # if new_hash != old_hash:
            #     iface_parsed: Interface = parse_cli_to_model(iface_cli, Interface)
            #     iface, created, changed = upsert_interface(nb=nb, device_id=device.id, if_name=iface_name, description=iface_parsed.description)
            #
            #     # Oczyścić interfejś od "starych" IP
            #     clear_ips(nb, iface_parsed.ipv4, iface)
            #
            #     is_ok: bool = True
            #
            #     for ip in iface_parsed.ipv4:
            #         try:
            #             nb_ip = get_or_create_ip(nb, device, ip.address, ip.is_primary, iface)
            #         except Exception as e:
            #             is_ok = False
            #             continue
            #
            #     if is_ok:
            #         # Hash interfejsu zapisuje wyłącznie wtedy, gdy wszystkie dane zostały pomyślnie zaktualizowane.
            #         iface, created, changed = upsert_interface(nb, device.id, iface_name, description=iface_parsed.description, cli_hash=new_hash)
            #
            #         if changed:
            #             print(f"Interface {iface.name} has changed")

    except Exception as e:
        raise DeviceEnsureError(f"Failed to collect facts for '{hostname}': {e}") from e

def chunk_ips(start_ip: str, end_ip: str, chunk_size: int):
    a = int(IPv4Address(start_ip))
    b = int(IPv4Address(end_ip))
    cur = a
    while cur <= b:
        chunk = []
        for _ in range(chunk_size):
            if cur > b:
                break
            chunk.append(str(IPv4Address(cur)))
            cur += 1
        yield chunk

MAX_WORKERS = 10

if __name__ == "__main__":
    start_ip = "172.16.2.245"
    end_ip = "172.16.2.245"

    CHUNK_SIZE = 16

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        futures = []
        for chunk in chunk_ips(start_ip, end_ip, CHUNK_SIZE):
            futures.append(ex.submit(lambda c=chunk: [start(ip) for ip in c]))

        for fut in as_completed(futures):
            try:
                fut.result()
            except Exception as e:
                print("Task failed:", e)

