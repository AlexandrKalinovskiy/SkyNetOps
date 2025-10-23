class DeviceEnsureError(Exception): 
    pass
class NetBoxCreateError(Exception):
    pass

from models import Facts
from .site import get_or_create_site
from .manufacturer import get_or_create_manufacturer
from .device_role import get_or_create_device_role
from .device_type import get_or_create_device_type
from .platform import get_or_create_platform

def get_or_create_device(nb, *, name: str, site_id: int, role_id: int, device_type_id: int,
                         platform_id: int, status: str = "active", serial_number: str):
    try:
        dev = nb.dcim.devices.get(name=name)
        if dev:
            return dev, False
        payload = {
            "name": name,
            "site": site_id,
            "role": role_id,
            "platform": platform_id,
            "device_type": device_type_id,
            "serial": serial_number,
            "status": status,
        }
        dev = nb.dcim.devices.create(payload)
        if not dev:
            raise NetBoxCreateError(f"NetBox did not return a device for name={name}")
        
        return dev, True
    except Exception as e:
        raise NetBoxCreateError(f"get_or_create_device(name={name}) failed: {e}") from e

# --- HIGH-LEVEL ORCHESTRATOR ---
def ensure_device_registered(
    nb,
    device_name,
    site_name: str = "LAB-DC",
    site_slug: str = "lab-dc",
    facts: Facts = None
):
    """
    If the device exists — return (device, False).
    If it does not exist — retrieve facts from the device, create dependencies in NetBox and the device: (device, True).
    Raises DeviceEnsureError on failure.
    """
    # 1. Quick exit if it already exists
    dev = nb.dcim.devices.get(name=device_name)
    if dev:
        return dev, False
    elif facts == {}:
        return None, False

    # 2. Create/get dependent objects
    try:
        site = get_or_create_site(nb, site_name, site_slug)
        manu = get_or_create_manufacturer(nb, facts.vendor, facts.vendor.lower().replace(" ", "-"))
        plat = get_or_create_platform(nb, facts.platform)
        role = get_or_create_device_role(nb, facts.device_role, facts.device_role.lower().replace(" ", "-"))
        dtype = get_or_create_device_type(nb, facts.model, manu.id)
    except Exception as e:
        raise DeviceEnsureError(f"Failed to prepare dependencies in NetBox for '{device_name}': {e}") from e

    # 3. Device
    try:
        device, created = get_or_create_device(
            nb,
            name=device_name,
            device_type_id=dtype.id,
            role_id=role.id,
            site_id=site.id,
            platform_id=plat.id,
            status="active",
            serial_number=facts.serial_number
        )
        return device, created
    except Exception as e:
        raise DeviceEnsureError(f"Failed to create device '{device_name}': {e}") from e