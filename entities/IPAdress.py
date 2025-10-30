from pydantic import BaseModel, Field, computed_field, field_validator
import ipaddress


class IPAddress(BaseModel):
    ip: str = Field(..., description="IPv4 or IPv6 address in standard format")
    mask: str = Field(..., description="Subnet mask, e.g. 255.255.255.0 or /24")
    is_primary: bool = Field(default=False, description="Indicates if the address is primary")

    @field_validator("mask", mode="before")
    def normalize_mask(cls, v):
        """Convert numeric masks to CIDR-style if necessary"""
        if isinstance(v, int):
            return f"/{v}"
        if isinstance(v, str) and v.startswith("/"):
            return v
        try:
            # Convert dotted mask to prefix length (e.g. 255.255.255.0 -> /24)
            return f"/{ipaddress.IPv4Network(f'0.0.0.0/{v}').prefixlen}"
        except Exception:
            raise ValueError(f"Invalid mask format: {v}")

    @computed_field  # field is automatically computed and returned in .model_dump()
    @property
    def cidr(self) -> str:
        """Return combined IP/mask in CIDR notation"""
        try:
            return str(ipaddress.ip_interface(f"{self.ip}{self.mask}"))
        except ValueError:
            raise ValueError(f"Invalid IP or mask: {self.ip}{self.mask}")


if __name__ == "__main__":
    # Simple test block
    addr = IPAddress(ip="192.168.10.5", mask="255.255.255.254", is_primary=True)
    print(addr)
    print("CIDR:", addr.cidr)