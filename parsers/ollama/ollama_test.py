from typing import Optional, Literal

from ollama import chat
from pydantic import BaseModel, Field
from enum import Enum

class DeviceRole(str, Enum):
    switch = "switch"
    router = "router"
    server = "server"
    firewall = "firewall"

class Pet(BaseModel):
    hostname: Optional[str] = Field(
        description="Hostname of the device."
    )
    model_name: str
    network_device_role: Optional[Literal["switch", "router", "server", "firewall"]] = Field(
        default="unknown",
        description="Network device role. Must be one of: switch, router, server, firewall."
    )
    serial_number: Optional[str] = Field(
        description="Serial number of the device."
    )

class PetList(BaseModel):
    pets: list[Pet]

file_path = "../prompts/prompt_main.txt"

section_cli = """
FortiGate-60E # get system status
Version: FortiGate-60E v7.0.12,build0568,230825 (GA)
Virus-DB: 108.0.34567(2023-08-25 02:28)
Extended DB: 108.0.45678(2023-08-25 04:29)
Extreme DB: 1.00000(2018-04-09 18:07)
IPS-DB: 7.00942(2023-08-25 05:42)
Industrial-DB: 7.00942(2023-08-25 05:42)
IPS-ETDB: 0.00000(2001-01-01 00:00)
APP-DB: 7.00942(2023-08-25 05:42)
INDUSTRIAL-APP-DB: 7.00942(2023-08-25 05:42)
Serial-Number: FG60ETK21012345
BIOS version: 04000028
System Part-Number: P12345-01
Hostname: FG-Branch-01
Operation Mode: NAT
Current virtual domain: root
Max number of virtual domains: 10
Virtual domains status: 1 in NAT mode, 0 in TP mode
Virtual domain configuration: disable
FIPS-CC mode: disable
Current HA mode: standalone
Branch Point: 0568
Release Version Information: GA
FortiOS x86-64
System time: Thu Oct 26 14:22:51 2023
uptime: 81 days, 22 hours, 37 minutes
"""
with open(file_path, "r", encoding="utf-8") as f:
    SYSTEM_PROMPT = f.read()

SYSTEM_PROMPT = """
You extract a structured JSON object from raw network CLI. 
Infer "device_role" strictly as one of: ["switch","router","server","firewall"].
If uncertain, return null. Do not invent values. Base the decision on model names and keywords:
- switch: "Switch Ports", "Catalyst", "WS-C...", "C2960X", "C9200", "C9300"
- router: "ISR", "ASR", "Integrated Services Router"
- firewall: "ASA", "Adaptive Security Appliance", "Firepower", "FTD", "FortiGate"
- server: "Dell", "HPE", "Supermicro", "iDRAC", "IPMI"

Return only JSON: {"model_name": str, "device_role": "switch"|"router"|"server"|"firewall"|null}
"""

response = chat(
    messages=[
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": section_cli }
    ],
    model='llama3.1:8b',
    format=Pet.model_json_schema(),
)

pets = Pet.model_validate_json(response.message.content)
print(pets)