from typing import Optional, Set, Dict, Iterable

def _units_occupied_by_device(top_u: int, height: int) -> Iterable[int]:
    """
    Given a device placed with its 'top' at U=top_u and having 'height' units,
    return all occupied U positions (descending), e.g. top_u=42, height=2 -> [42, 41].
    """
    for u in range(top_u, top_u - height, -1):
        yield u

def _build_occupancy_map(nb, rack_id: int) -> Dict[str, Set[int]]:
    """
    Build an occupancy map for the rack:
      returns {"front": {occupied_U...}, "rear": {occupied_U...}}
    Fetches all devices in the rack and marks their occupied Us based on device_type.u_height.
    """
    occ = {"front": set(), "rear": set()}
    devices = nb.dcim.devices.filter(rack_id=rack_id, limit=0)

    for dev in devices:
        # Skip devices without positional placement (0U or not mounted)
        if getattr(dev, "position", None) is None or getattr(dev, "face", None) is None:
            continue

        # Resolve device type height (u_height)
        dt_id = getattr(dev, "device_type", None)
        if not dt_id:
            continue
        # When using pynetbox, device_type may be an ID or an object depending on expansions.
        # We fetch explicitly to be safe.
        dt = nb.dcim.device_types.get(dt_id if isinstance(dt_id, int) else dt_id.id)
        if dt is None:
            continue
        height = getattr(dt, "u_height", None)
        if not isinstance(height, int) or height <= 0:
            # Treat unknown height as 1U fallback (conservative)
            height = 1

        top_u = int(dev.position)
        face = str(dev.face).lower()  # "front" or "rear"
        if face not in occ:
            continue

        for u in _units_occupied_by_device(top_u, height):
            occ[face].add(u)

    return occ

def _find_first_free_top_u_from_top(
    rack_u_height: int,
    device_u_height: int,
    occupied: Set[int],
) -> Optional[int]:
    """
    Scan from the top of the rack (highest U) downward for the first contiguous
    block of free Us that can fit 'device_u_height'. Return the 'top' U position.
    """
    if device_u_height <= 0:
        return None

    # We attempt top positions from rack_u_height down to device_u_height
    # so that the lowest occupied U would be >= 1
    for candidate_top in range(rack_u_height, device_u_height - 1, -1):
        block = set(range(candidate_top, candidate_top - device_u_height, -1))
        if block.isdisjoint(occupied):
            return candidate_top
    return None

def _get_site_id_by_name(nb, site_name: str) -> int:
    """Resolve Site.id by its name (exact)."""
    site = nb.dcim.sites.get(name=site_name)
    return site.id if site else 0

def _get_or_create_rack(
    nb,
    rack_name: str,
    site_id: int,
    location_id: Optional[int] = None,
    u_height: int = 42,
    width: int = 19,  # inches; NetBox default is usually 19
):
    """
    Get a Rack by (name, site). If not present, create it with the provided parameters.
    Returns the Rack object.
    """
    rack = nb.dcim.racks.get(name=rack_name)

    if rack is None:
        # Build payload for rack creation; adjust fields to match your NetBox constraints/policies.
        payload = {
            "name": rack_name,
            "site": site_id,
            "u_height": u_height,
            "width": width,
            # Optional fields you may want to set by policy:
            # "status": "active",         # if your NetBox uses statuses for racks
            # "role": <role_id>,          # if you use rack roles
            # "tenant": <tenant_id>,      # if multi-tenant
            # "serial": "", "asset_tag": ""
        }
        if location_id:
            payload["location"] = location_id

        rack = nb.dcim.racks.create(payload)
        if not rack:
            raise ValueError(f"Failed to create rack {rack_name!r} in site ID {site_id}")
        return rack

    return rack

def assign_device_to_rack(
    nb,
    device_name: str,
    rack_name: str,
    face: str = "front",
    force_site_sync: bool = True,
    force_location_sync: bool = True,
) -> int:
    """
    Place an existing device into the given rack at the first free U position from the top.

    Behavior:
      1) Resolves rack and device by names.
      2) Ensures device.site/location match the rack (optional sync).
      3) Computes current occupancy of the rack (per face).
      4) Finds the first free contiguous block from the top that fits device.u_height.
      5) Updates the device with rack, position, and face.

    Args:
        device_name: NetBox Device.name (exact).
        rack_name: NetBox Rack.name (exact).
        face: "front" or "rear".
        force_site_sync: If True, align device.site to rack.site when different.
        force_location_sync: If True, align device.location to rack.location when different.

    Returns:
        The assigned top U position (int).

    Raises:
        ValueError: On not found entities, 0U devices, no free space, or invalid args.
    """
    face = face.lower()
    if face not in {"front", "rear"}:
        raise ValueError("face must be 'front' or 'rear'.")

    # 1) Resolve rack and device
    site_id = _get_site_id_by_name(nb,"LAB-DC")
    rack = _get_or_create_rack(nb, rack_name, site_id=site_id)

    device = nb.dcim.devices.get(name=device_name)
    if device is None:
        raise ValueError(f"Device not found by name: {device_name!r}")

    # Resolve device type to know u_height (0U devices cannot be placed in U space)
    dt_id = getattr(device, "device_type", None)
    if not dt_id:
        raise ValueError("Device has no device_type associated.")
    dt = nb.dcim.device_types.get(dt_id if isinstance(dt_id, int) else dt_id.id)
    if dt is None:
        raise ValueError("Device type not found.")

    dev_height_raw = getattr(dt, "u_height", None)

    try:
        dev_height = int(dev_height_raw)
    except (TypeError, ValueError):
        raise ValueError(f"Device type 'u_height' is invalid: {dev_height_raw!r}")

    if dev_height <= 0:
        raise ValueError(f"Device type 'u_height' must be positive, got {dev_height}")

    # 2) Optional site/location synchronization
    payload = {"rack": rack.id}

    rack_site_id = rack.site.id if getattr(rack, "site", None) else None
    device_site_id = device.site.id if getattr(device, "site", None) else None
    if rack_site_id is None:
        raise ValueError(f"Rack {rack_name!r} has no site set; cannot attach device reliably.")

    if device_site_id != rack_site_id:
        if force_site_sync:
            payload["site"] = rack_site_id
        else:
            raise ValueError(
                f"Device site ({device.site.name if device_site_id else 'None'}) "
                f"does not match rack site ({rack.site.name}); set force_site_sync=True to auto-fix."
            )

    rack_location_id = rack.location.id if getattr(rack, "location", None) else None
    device_location_id = device.location.id if getattr(device, "location", None) else None
    if rack_location_id and device_location_id != rack_location_id and force_location_sync:
        payload["location"] = rack_location_id

    # 3) Build occupancy map and find first free position on selected face
    rack_u = getattr(rack, "u_height", None)
    if not isinstance(rack_u, int) or rack_u <= 0:
        raise ValueError("Rack 'u_height' is not set or invalid.")

    occ = _build_occupancy_map(nb, rack.id)
    occupied_face = occ.get(face, set())

    pos = _find_first_free_top_u_from_top(rack_u_height=rack_u,
                                          device_u_height=dev_height,
                                          occupied=occupied_face)
    if pos is None:
        raise ValueError(
            f"No contiguous free space for {dev_height}U device in rack {rack_name!r} on {face}."
        )

    # 4) Update device with position and face
    payload["position"] = pos
    payload["face"] = face

    ok = device.update(payload)
    if not ok:
        raise ValueError(f"Failed to update device {device_name!r} with payload: {payload}")

    print(f"[OK] Placed {device_name!r} into rack {rack_name!r} at U{pos} ({face}), height={dev_height}U.")
    return pos


# --- Example usage ---
# assign_device_to_rack_first_free("SG-ZD1-SW1", "ZD1", face="front")
# assign_device_to_rack_first_free("CORE-S2-3-SW2", "S2-3", face="rear")
# assign_device_to_rack_first_free("KROS1-AGG-SW", "KROS1", face="front")
