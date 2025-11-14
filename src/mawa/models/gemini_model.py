import os
from typing import Any, Optional

from dotenv import load_dotenv
from google import genai
from google.genai.types import (
    GenerateContentConfig,
    GenerateContentResponse,
    Part,
)

from mawa.config import GEMINI_FLASH_MODEL, GEMINI_PRO_MODEL

load_dotenv()


PRICING = {
    "gemini-2.5-pro": {
        "input_up_to_200k": 1.25,  # $ par 1M tokens
        "input_200k_to_1M": 2.50,
        "output_up_to_200k": 10.00,
        "output_200k_to_1M": 15.00,
        "cache_up_to_200k": 0.125,
        "cache_200k_to_1M": 0.25,
        "cache_storage": 4.50,  # $ per 1M tokens
    },
    "gemini-2.5-flash": {
        "input": 0.30,
        "output": 2.50,
        "cache": 0.03,
        "cache_storage": 1.00,  # $ per 1M tokens
    },
}


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

    def input_tokens_metadata(self, prompt: list[Part]) -> dict[str, Any]:
        """
        Calculate the input cost based on the input tokens.
        Prices updated (check on https://ai.google.dev/pricing)
        """
        tokens = self.client.models.count_tokens(
            model=self.model, contents=prompt
        ).model_dump()
        input_tokens = tokens["total_tokens"]
        cached_tokens = tokens["cached_content_token_count"]
        cached_tokens = cached_tokens if cached_tokens is not None else 0

        cost = 0
        hourly_cache_cost = 0

        if self.model == "gemini-2.5-pro":
            prices = PRICING["gemini-2.5-pro"]
            if input_tokens <= 200_000:
                cost += input_tokens * prices["input_up_to_200k"]
            else:
                cost += input_tokens * prices["input_200k_to_1M"]

            if cached_tokens <= 200_000:
                cost += cached_tokens * prices["cache_up_to_200k"]
            else:
                cost += cached_tokens * prices["cache_200k_to_1M"]

            hourly_cache_cost = cached_tokens * prices["cache_storage"]

        elif self.model == "gemini-2.5-flash":
            prices = PRICING["gemini-2.5-flash"]
            cost += input_tokens * prices["input"]
            cost += cached_tokens * prices["cache"]
            hourly_cache_cost = cached_tokens * prices["cache_storage"]

        tokens["token_cost"] = cost / 1_000_000
        tokens["hourly_cache_storage_cost"] = hourly_cache_cost / 1_000_000
        return tokens


def _string_to_part(elem: str | Part | None) -> Part:
    """Convert a string to a Part if it is a string"""
    return Part(text=elem) if isinstance(elem, str) else elem
