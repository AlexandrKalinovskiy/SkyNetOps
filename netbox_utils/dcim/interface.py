from pynetbox.core.query import RequestError
from typing import Optional, Dict, Any, Tuple
from netbox_utils.utils import first, iface_type_from_name, _norm_mac

def ensure_primary_mac(nb, iface, mac: str) -> bool:
    """
    Upewnia się, że w NetBox istnieje obiekt MAC (dcim/mac-addresses),
    jest przypięty do danego interfejsu i ustawiony jako primary (FK) na interfejsie.
    Zwraca True, jeśli coś zmieniono.
    """
    changed = False
    want = _norm_mac(mac)
    if not want:
        return False

    # 1) Znajdź lub utwórz obiekt MAC (UWAGA: klucz to 'mac_address')
    mac_obj = first(nb.dcim.mac_addresses.filter(mac_address=want))
    if mac_obj is None:
        mac_obj = nb.dcim.mac_addresses.create({
            "mac_address": want,
            "assigned_object_type": "dcim.interface",
            "assigned_object_id": iface.id,
        })
        changed = True
    else:
        # 2) Jeśli istnieje, upewnij się, że jest przypięty do TEGO interfejsu
        ao_type = getattr(mac_obj, "assigned_object_type", None)
        ao_id = getattr(mac_obj, "assigned_object_id", None)
        if ao_type != "dcim.interface" or ao_id != iface.id:
            mac_obj.update({
                "assigned_object_type": "dcim.interface",
                "assigned_object_id": iface.id,
            })
            changed = True

    # 3) Ustaw primary na interfejsie przez FK 'primary_mac' (ID obiektu MAC)
    current_primary_id = getattr(getattr(iface, "primary_mac", None), "id", None)
    if current_primary_id != mac_obj.id:
        iface.update({"primary_mac": mac_obj.id})
        changed = True

    return changed


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
    iface = first(nb.dcim.interfaces.filter(device_id=device_id, name=if_name))

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
            iface = next(iter(nb.dcim.interfaces.filter(device_id=device_id, name=if_name)), None)
            if iface is None:
                raise
            created = False
    else:
        created = False

    patch: Dict[str, Any] = {}

    if description is not None and (iface.description or "") != description:
        patch["description"] = description

    if enabled is not None and bool(iface.enabled) != bool(enabled):
        patch["enabled"] = bool(enabled)

    if mtu is not None:
        new_mtu = int(mtu)
        if iface.mtu != new_mtu:
            patch["mtu"] = new_mtu

    if cli_hash is not None:
        cf = dict(getattr(iface, "custom_fields", {}) or {})
        if cf.get("cli_hash") != cli_hash:
            cf["cli_hash"] = cli_hash
            patch["custom_fields"] = cf

    changed = False
    if patch:
        iface.update(patch)
        # odśwież obiekt
        iface = next(iter(nb.dcim.interfaces.filter(device_id=device_id, name=if_name)), iface)
        changed = True

    if mac_address:
        if ensure_primary_mac(nb, iface, mac_address):
            # odśwież po zmianach
            iface = next(iter(nb.dcim.interfaces.filter(device_id=device_id, name=if_name)), iface)
            changed = True or changed

    return iface, created, changed
