from ..utils import first

def get_or_create_device_role(nb, name: str, slug: str):
    role = nb.dcim.device_roles.get(slug=slug)
    if role:
        return role
    role = first(nb.dcim.device_roles.filter(name=name))
    return role or nb.dcim.device_roles.create({"name": name, "slug": slug})