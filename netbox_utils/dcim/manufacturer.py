from ..utils import first

def get_or_create_manufacturer(nb, name: str, slug: str):
    manu = nb.dcim.manufacturers.get(slug=slug)
    if manu:
        return manu
    manu = first(nb.dcim.manufacturers.filter(name=name))
    return manu or nb.dcim.manufacturers.create({"name": name, "slug": slug})