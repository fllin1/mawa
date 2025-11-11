import os
from typing import Optional

from dotenv import load_dotenv
from google import genai
from google.genai.types import (
    GenerateContentResponse,
    Part,
    GenerateContentConfig,
)

from mawa.config import GEMINI_FLASH_MODEL, GEMINI_PRO_MODEL

load_dotenv()


class GeminiModel:
    def __init__(self, model: str):
        self.client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        if model == "flash":
            self.model = GEMINI_FLASH_MODEL
        elif model == "pro":
            self.model = GEMINI_PRO_MODEL
        else:
            raise ValueError(f"Invalid model: {model}")

    def generate_content(
        self,
        prompt: list[Part | str],
        system_prompt: Optional[Part | str] = None,
        json_schema: Optional[dict] = None,
    ) -> GenerateContentResponse:
        """Generate text with structured output using Gemini Flash

        Args:
            prompt (list[Part]): The prompt to use to generate the text
            json_schema (dict): The JSON schema to use to generate the text
            system_prompt (Optional[Part | str]): The system prompt to use to generate the text
        """
        config = GenerateContentConfig(
            system_instruction=_string_to_part(system_prompt),
            response_mime_type="application/json",
            response_json_schema=json_schema,
        )
        print(f"Request sent to {self.model}...")
        response = self.client.models.generate_content(
            model=self.model, contents=prompt, config=config
        )
        return response


def _string_to_part(elem: str | Part | None) -> Part:
    """Convert a string to a Part if it is a string"""
    return Part(text=elem) if isinstance(elem, str) else elem
