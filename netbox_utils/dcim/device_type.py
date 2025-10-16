from netbox_utils.utils import first, _slugify
from pynetbox.core.query import RequestError

def get_or_create_device_type(nb, model: str, manufacturer_id: int):
    # 1) jest już taki typ? (najpewniej po parze manufacturer+model)
    dt = first(
        nb.dcim.device_types.filter(model=model, manufacturer_id=manufacturer_id)
    )
    if dt:
        return dt

    # 2) wygeneruj bazowy slug
    base = _slugify(model)
    slug = base

    # 3) upewnij się, że slug nie koliduje w ramach tego producenta
    #    (jeśli NetBox ma unikalność globalną slugów, pętla też to ogarnie)
    i = 2
    while True:
        conflict = first(
            nb.dcim.device_types.filter(slug=slug, manufacturer_id=manufacturer_id)
        )
        if not conflict:
            break
        slug = f"{base}-{i}"
        i += 1

    payload = {
        "model": model,
        "manufacturer": manufacturer_id,  # ID producenta
        "slug": slug,
    }

    try:
        return nb.dcim.device_types.create(payload)
    except RequestError as e:
        # jeśli backend i tak krzyczy o slugu/unikalności, spróbuj kolejny sufiks
        msg = str(e).lower()
        if "slug" in msg or "already exists" in msg or "unique" in msg:
            # dodatkowe zabezpieczenie – spróbuj jeszcze raz z kolejnym sufiksem
            while True:
                slug = f"{base}-{i}"
                i += 1
                payload["slug"] = slug
                try:
                    return nb.dcim.device_types.create(payload)
                except RequestError:
                    continue
        raise