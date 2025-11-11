import json
import os

from dotenv import load_dotenv
from google import genai
from google.genai.types import GenerateContentConfig

from mawa.config import CONFIG_DIR

load_dotenv()

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

with open(CONFIG_DIR / "schemas" / "test_schema.json", "r") as f:
    schema = json.load(f)

response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents="This is a test to test the JSON schema, return with minimal text to fill the schema.",
    config=GenerateContentConfig(
        response_mime_type="application/json",
        response_json_schema=schema,
    ),
)

print(response.text)
