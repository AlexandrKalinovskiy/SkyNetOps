from pynetbox.core.query import RequestError
from typing import List, Optional, Sequence, Union, Literal, Dict, Any, Tuple
from netbox_utils.utils import first, iface_type_from_name, _norm_mac

def upsert_interface(
    nb,
    device_id: int,
    if_name: str,
    *,
    description: Optional[str] = None,
    enabled: Optional[bool] = None,
    mtu: Optional[int] = None,
    mac_address: Optional[str] = None,
    cli_hash: Optional[str] = None,
) -> Tuple[Any, bool, bool]:
    """
        Returns: (iface, created, changed)
        created: True if the interface was created
        changed: True if any field was updated
    """
    # 1) Searching for the interface
    iface = first(nb.dcim.interfaces.filter(device_id=device_id, name=if_name))

    # 2) If it doesn’t exist – create a baseline (only what MUST be present)
    if iface is None:
        payload = {
            "device": device_id,
            "name": if_name,
            "type": iface_type_from_name(if_name),
            "enabled": True if enabled is None else bool(enabled),
        }
        try:
            iface = nb.dcim.interfaces.create(payload)
            created = True
        except RequestError:
            # Possible race condition – try fetching again
            iface = next(iter(nb.dcim.interfaces.filter(device_id=device_id, name=if_name)), None)
            if iface is None:
                raise
            created = False
    else:
        created = False

    # 3) Build a PATCH only for actual changes (idempotency)
    patch: Dict[str, Any] = {}

    if description is not None and (iface.description or "") != description:
        patch["description"] = description

    if enabled is not None and bool(iface.enabled) != bool(enabled):
        patch["enabled"] = bool(enabled)

    if mtu is not None:
        new_mtu = int(mtu)
        if iface.mtu != new_mtu:
            patch["mtu"] = new_mtu

    if mac_address is not None:
        want_mac = _norm_mac(mac_address)
        have_mac = _norm_mac(iface.mac_address) if getattr(iface, "mac_address", None) else None
        if want_mac and want_mac != have_mac:
            patch["mac_address"] = want_mac

    if cli_hash is not None:
        cf = dict(getattr(iface, "custom_fields", {}) or {})
        if cf.get("cli_hash") != cli_hash:
            cf["cli_hash"] = cli_hash
            patch["custom_fields"] = cf

    changed = bool(patch)
    if changed:
        iface.update(patch)
        # refresh (includes custom_fields)
        iface = next(iter(nb.dcim.interfaces.filter(device_id=device_id, name=if_name)), iface)

    return iface, created, changed