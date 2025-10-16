from netbox_utils.utils import first

def get_or_create_site(nb, name: str, slug: str):
    site = nb.dcim.sites.get(slug=slug)
    if site:
        return site
    # fallback po name
    site = first(nb.dcim.sites.filter(name=name))
    return site or nb.dcim.sites.create({"name": name, "slug": slug})