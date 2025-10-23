from openai import OpenAI
from typing import Type, TypeVar, Optional, Literal
from pydantic import BaseModel, Field
import os
from pathlib import Path
from dotenv import load_dotenv, find_dotenv

from models import Facts

T = TypeVar("T", bound=BaseModel)

def parse_cli_to_model(section_cli, schema: Type[T]):
    # Bezpieczne wyszukiwanie .env w górę od pliku startowego
    env_path = find_dotenv() or (Path(__file__).resolve().parent / ".env")
    load_dotenv(env_path)

    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    client = OpenAI(api_key=OPENAI_API_KEY)

    file_path = "parsers/prompts/prompt_main.txt"
    model = "gpt-4o-mini"

    with open(file_path, "r", encoding="utf-8") as f:
        SYSTEM_PROMPT = f.read()

    resp = client.responses.parse(
        model=model,
        input=[
            # {"role": "system", "content": "SYSTEM_PROMPT"},
            {"role": "user", "content": section_cli }
        ],
        text_format=schema,
        temperature=0                     # maksymalna deterministyczność
    )

    # Dostajesz już obiekt Pydantic:
    parsed: T = resp.output_parsed
    print(parsed.model_dump_json(indent=2, by_alias=True))

    return parsed

if __name__ == "__main__":
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
    class Pet(BaseModel):
        hostname: Optional[str] = Field(
            description="Hostname of the device."
        )
        model_name: str
        device_role: Optional[Literal["switch", "router", "server", "firewall"]] = Field(
            default=None,
            description="Network device role. Must be one of: switch, router, server, firewall."
        )
        number: Optional[str] = Field(
            description="Serial number of this device"
        )

    parsed = parse_cli_to_model(section_cli, Pet)
