from models import Interface
from netbox_utils.utils import is_management_interface, is_primary_interface

def get_or_create_ip(
    nb, device, address: str, is_primary: bool, interface: Interface, status: str = "active"
):
    # 1. Check if the IP already exists
    results = nb.ipam.ip_addresses.filter(address=address)
    existing_ip = next(iter(results), None)  # Take the first result or None

    if existing_ip:
        if existing_ip.assigned_object is None:
            print("The IP is not assigned to any interface")
            existing_ip.assigned_object_type = "dcim.interface"
            existing_ip.assigned_object_id = interface.id
            existing_ip.save()
            # console.print(f"[bold blue]ℹ Assigned IP[/] [magenta]{existing_ip.address}[/] to interface [cyan]{interface.name}[/]")
        else:
            iface = nb.dcim.interfaces.get(existing_ip.assigned_object_id)
            device = nb.dcim.devices.get(iface.device.id)
            # raise Exception(f"IP {address} is assigned to: {device.name} ({existing_ip.assigned_object})")
    else:
        existing_ip = nb.ipam.ip_addresses.create(
            {
                "address": address,
                "status": status,
                "assigned_object_id": interface.id,
                "assigned_object_type": "dcim.interface",
            }
        )

        # console.print(f"[bold blue]ℹ Assigned IP[/] [magenta]{existing_ip.address}[/] to interface [cyan]{interface.name}[/]")

    # If this is a management interface - set this IP as primary
    if is_management_interface(interface.name, interface.description, address):
        device.update({"oob_ip": existing_ip.id})
        return existing_ip

    if is_primary_interface(interface.name, interface.description):
        device.update({"primary_ip4": existing_ip.id})

    return existing_ip