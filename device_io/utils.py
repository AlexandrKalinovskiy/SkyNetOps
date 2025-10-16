import re

def extract_interface_section(cli_text: str, interface_name: str) -> str:
    """
    Wyciąga sekcję interface <name> ... aż do następnego interface lub końca pliku.
    """
    pattern = rf"^interface {re.escape(interface_name)}[\s\S]*?(?=^interface |\Z)"
    match = re.search(pattern, cli_text, re.MULTILINE)
    return match.group(0).strip() if match else ""