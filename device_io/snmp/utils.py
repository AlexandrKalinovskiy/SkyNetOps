def decode_snmp_octetstring(value: str) -> str:
    if isinstance(value, str) and value.startswith("0x"):
        hexstr = value[2:]
        try:
            return bytes.fromhex(hexstr).decode("utf-8", errors="replace")
        except Exception:
            return bytes.fromhex(hexstr).decode("latin-1", errors="replace")
    return value