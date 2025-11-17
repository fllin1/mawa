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
            system_instruction=system_prompt,
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

        tokens = self._calculate_cost(tokens)
        return tokens

    def output_tokens_metadata(self, tokens: dict) -> dict[str, Any]:
        """
        Calculate the output cost based on the output tokens metadata.
        Prices updated (check on https://ai.google.dev/pricing)
        """
        tokens = self._calculate_cost(tokens)
        return tokens

    # Helper functions

    def _calculate_cost(self, tokens: dict) -> float:
        if self.model not in PRICING:
            return tokens

        prices = PRICING[self.model]

        cached_tokens = tokens.get("cached_content_token_count", 0)
        cached_tokens = cached_tokens if cached_tokens is not None else 0
        time_taken = tokens.get("time_taken", 0)

        if "prompt_token_count" in tokens:
            input_tokens = tokens["prompt_token_count"]
        else:
            input_tokens = tokens.get("total_tokens", 0) - cached_tokens

        output_tokens = tokens.get("candidates_token_count", 0)
        output_tokens += tokens.get("thoughts_token_count", 0)

        input_cost = 0
        output_cost = 0
        hourly_cache_cost = 0

        if self.model == "gemini-2.5-pro":
            if input_tokens <= 200_000:
                input_cost += input_tokens * prices["input_up_to_200k"]
            else:
                input_cost += input_tokens * prices["input_200k_to_1M"]

            if cached_tokens <= 200_000:
                input_cost += cached_tokens * prices["cache_up_to_200k"]
            else:
                input_cost += cached_tokens * prices["cache_200k_to_1M"]

            if output_tokens <= 200_000:
                output_cost += output_tokens * prices["output_up_to_200k"]
            else:
                output_cost += output_tokens * prices["output_200k_to_1M"]

            hourly_cache_cost = cached_tokens * prices["cache_storage"]
            storage_cost = time_taken * hourly_cache_cost / 3600

        elif self.model == "gemini-2.5-flash":
            input_cost += input_tokens * prices["input"]
            input_cost += cached_tokens * prices["cache"]
            output_cost += output_tokens * prices["output"]
            hourly_cache_cost = cached_tokens * prices["cache_storage"]
            storage_cost = time_taken * hourly_cache_cost / 3600

        tokens["input_token_cost"] = (input_cost) / 1_000_000
        tokens["output_token_cost"] = (output_cost) / 1_000_000
        tokens["total_token_cost"] = (input_cost + output_cost) / 1_000_000
        tokens["hourly_cache_storage_cost"] = hourly_cache_cost / 1_000_000
        tokens["storage_cost"] = storage_cost / 1_000_000

        return tokens
