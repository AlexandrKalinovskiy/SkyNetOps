class DeviceEnsureError(Exception):
    pass

class NetBoxCreateError(Exception):
    pass

import pynetbox
from device_io.snmp import snmp_hostname, snmp_sysdescr, snmp_model, snmp_serial, snmp_interfaces, snmp_device_role
from rich.console import Console
from netbox_utils.dcim import rack
from netbox_utils.dcim.device import ensure_device_registered, get_interfaces_hash, set_interfaces_hash
from netbox_utils.dcim.interface import upsert_interface
from netbox_utils.utils import sha256_of, clear_ips, is_valid_ip
from parsers.ai_parser import parse_cli_to_model
from models import DetectPlatform, DetectDeviceRole, DetectVendor
from entities.Facts import Facts
from netbox_utils.ipam.ip import get_or_create_ip
from concurrent.futures import ThreadPoolExecutor, as_completed
from ipaddress import IPv4Address
from netbox_utils.helpers import rack_parser
import threading
import os

console = Console()

_thread_local = threading.local()

def get_nb():
    """Return a NetBox client stored in thread-local storage (one per thread)."""
    nb = getattr(_thread_local, "nb", None)
    if nb is None:
        # Prefer env vars; avoid hardcoding secrets
        url = os.getenv("NETBOX_URL", "http://10.8.0.1:8000")
        token = os.getenv("NETBOX_TOKEN", "97c50a928fff461721ec0eeb826f6e54eac6826e")
        nb = pynetbox.api(url, token=token)
        # Optional: fail fast (uncomment if helpful)
        # nb.status()
        _thread_local.nb = nb
    return nb

def start(host: str):
    # Connecting to NetBox
    nb = get_nb()  # reuse NetBox client within the same thread

    console.print(f"[bold]🔌Check IP: [/] {host}")
    hostname = snmp_hostname.get(host)
    if not hostname:
        return

    rack_name = rack_parser.get(hostname)
    print(f"{hostname} -> {rack_name}")

    # =========== Collect facts and create device in NetBox ==============
    try:
        device, created = ensure_device_registered(nb, device_name=hostname, facts={})

        if not device and not created:
            # Device not exist
            sys_descr = snmp_sysdescr.get(host)
            model = snmp_model.get(host)
            serial = snmp_serial.get(host)
            platform_detect = parse_cli_to_model(sys_descr, DetectPlatform)
            role_detect = parse_cli_to_model(f"model: {model}\nplatform: {platform_detect}\nsysDescr: {sys_descr}",
                                             DetectDeviceRole)
            vendor_detect = parse_cli_to_model(sys_descr, DetectVendor)
            print(platform_detect)
            facts = Facts(
                hostname=hostname,
                vendor=vendor_detect.vendor,
                model=model,
                serial_number=serial or "none",
                platform=platform_detect.platform,
                device_role=role_detect.role,
            )
            device, created = ensure_device_registered(nb, device_name=hostname, facts=facts, mgmt_address=host)

        if created:
            # Add virtual mgmt interface for 172.16.2.0
            iface, created, changed = upsert_interface(nb=nb, device_id=device.id, if_name="virtual-mgmt",
                                                       description="virtual-mgmt")
            nb_ip = get_or_create_ip(nb, device, host, False, interface=iface)
            console.print(f"[green]✔ Created device[/] [yellow]{device.name} {host}[/] in NetBox")
            if rack_name:
                rack.assign_device_to_rack(nb, device, rack_name)
        else:
            console.print(f"[cyan]ℹ Device exist[/] [yellow]{device.name} {host}[/]")


    except Exception as e:
        raise DeviceEnsureError(f"Failed to collect facts for '{hostname}': {e}") from e

    # =========== Create and check interfaces ==============
    try:
        interfaces, interfaces_hash = snmp_interfaces.get(host)
        nb_interfaces_hash = get_interfaces_hash(device)

        if nb_interfaces_hash != interfaces_hash:
            for info in interfaces:
                iface = info.get("ifDescr", "unknown")
                desc = info.get("description", "")
                ip_adresses = info.get("ips", [])
                mac = info.get("mac", "")

                print(f"{iface} : {mac}\n")

                iface, created, changed = upsert_interface(nb=nb, device_id=device.id, if_name=iface, mac_address=mac, description=desc)

                # Here, the remaining addresses are added
                for ip_data in ip_adresses:
                    ip = ip_data.get("ip", "")
                    if created or changed:
                        if is_valid_ip(ip):
                            print(f"Set IP: {ip}")
                            nb_ip = get_or_create_ip(nb, device, ip, True, iface)

                # Adds the management IP address to the device
                # nb_ip = get_or_create_ip(nb, device, host, False, iface)
            set_interfaces_hash(device, interfaces_hash)
            return

        print(f"{hostname} : nb_interfaces_hash = interfaces_hash")
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
    start_ip = "172.16.2.111"
    end_ip = "172.16.2.111"

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

