from netbox_utils.utils import _slugify

def get_or_create_platform(nb, name: str):
    p = nb.dcim.platforms.get(name=name)
    if p:
        return p

    return nb.dcim.platforms.create({"name": name,"slug": _slugify(name)})