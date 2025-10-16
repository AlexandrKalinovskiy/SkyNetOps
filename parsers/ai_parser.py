from openai import OpenAI
from typing import Type, TypeVar
from pydantic import BaseModel
import os
from pathlib import Path
from dotenv import load_dotenv, find_dotenv

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
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": section_cli }
        ],
        text_format=schema,
        temperature=0                     # maksymalna deterministyczność
    )

    # Dostajesz już obiekt Pydantic:
    parsed: T = resp.output_parsed
    print(parsed.model_dump_json(indent=2, by_alias=True))

    return parsed
