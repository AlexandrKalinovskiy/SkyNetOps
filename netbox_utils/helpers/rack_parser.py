import re
from typing import Optional

# Regex patterns for all rack types
_RX_KROS = re.compile(r'\bK(?:ROS|ROSS)?[-_]?([12])\b', re.IGNORECASE)
_RX_S = re.compile(r'\bS(\d+)[-_](\d+)\b', re.IGNORECASE)
_RX_ZD = re.compile(r'\bZD(\d+)\b', re.IGNORECASE)


def get(hostname: str) -> Optional[str]:
    """
    Extracts rack name from a hostname.

    Supported formats:
      - K1/K2/KROS1/KROSS2 → KROS1/KROS2
      - ZD1..ZD7 → ZD#
      - S1-1..S10-9 (or S1_1) → S#-#

    Returns:
        A normalized rack name ('KROS#', 'ZD#', 'S#-#') or None if not found.
    """
    # Normalize the hostname: replace underscores with dashes and make it uppercase
    hn = hostname.replace("_", "-").upper()

    # 1️⃣ Match KROS racks (K1, K2, KROS1, KROSS2)
    if (m := _RX_KROS.search(hn)):
        num = int(m.group(1))
        if num in (1, 2):
            return f"KROS{num}"

    # 2️⃣ Match ZD racks (ZD1..ZD7)
    if (m := _RX_ZD.search(hn)):
        num = int(m.group(1))
        if 1 <= num <= 7:
            return f"ZD{num}"

    # 3️⃣ Match S racks (S1-1..S10-9 or S1_1)
    if (m := _RX_S.search(hn)):
        a, b = int(m.group(1)), int(m.group(2))
        if 1 <= a <= 10 and 1 <= b <= 9:
            return f"S{a}-{b}"

    # If nothing matched, return None
    return None

if __name__ == "__main__":
    # --- Example usage ---
    tests = [
        "SG-ZD1_SW1",
        "CORE-S1_2-SW2",
        "EDGE-S10-9-UPLINK",
        "NODE-K1-ACCESS",
        "KROSS2-EDGE-SW",
        "AGG-KROS1-X",
        "DIST-ZD8-FOO",  # Out of range
        "S11-1-test",  # Out of range
        "random"
    ]

    for h in tests:
        print(f"{h:25} -> {get(h)}")

