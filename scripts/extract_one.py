from dotenv import load_dotenv
import os
import json
import re

def clean_json_response(raw_text):
    """Strip markdown code fences and think blocks, return clean JSON string."""
    text = re.sub(r'<think>.*?</think>', '', raw_text, flags=re.DOTALL)
    text = text.strip()
    # remove ```json or ``` at start, ``` at end
    text = re.sub(r'^```(?:json)?\s*', '', text)
    text = re.sub(r'\s*```$', '', text)
    return text.strip()

load_dotenv()

image_path = "data/images/bill_01.jpg"

with open(image_path, "rb") as f:
    image_bytes = f.read()

from google import genai
from google.genai import types

client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))

EXTRACTION_PROMPT = """
Extract the following fields from this handwritten bill image.
Return ONLY valid JSON, no other text, no markdown code fences.
Use exactly these keys:
- vendor
- bill_number
- date (format YYYY-MM-DD, or null if not present/unreadable)
- amount (number only, no currency symbol)
- currency
- gst_details (a short plain text string summarizing any GST info visible, e.g. "GST 18% mentioned" or "none visible" -- do NOT return a nested object for this field)

If a field is not present or unreadable, use null for that field.
"""

resp = client.models.generate_content(
    model="gemini-3.6-flash",
    contents=[
        types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"),
        EXTRACTION_PROMPT
    ]
)

raw_text = resp.text
print("--- RAW RESPONSE ---")
print(raw_text)

# Try to parse it as JSON
try:
    parsed = json.loads(clean_json_response(raw_text))
    print("--- PARSED SUCCESSFULLY ---")
    print(parsed)
except json.JSONDecodeError as e:
    print("--- JSON PARSE FAILED ---")
    print("Error:", e)

import base64
import re

# --- Mistral ---
from mistralai.client import Mistral

image_b64 = base64.b64encode(image_bytes).decode("utf-8")

client_mistral = Mistral(api_key=os.getenv("MISTRAL_API_KEY"))
resp_mistral = client_mistral.chat.complete(
    model="pixtral-12b-2409",
    messages=[
        {
            "role": "user",
            "content": [
                {"type": "text", "text": EXTRACTION_PROMPT},
                {"type": "image_url", "image_url": f"data:image/jpeg;base64,{image_b64}"}
            ]
        }
    ]
)
raw_mistral = resp_mistral.choices[0].message.content
print("\n--- MISTRAL RAW ---")
print(raw_mistral)

try:
    parsed_mistral = json.loads(clean_json_response(raw_mistral))
    print("--- MISTRAL PARSED ---")
    print(parsed_mistral)
except json.JSONDecodeError as e:
    print("--- MISTRAL PARSE FAILED ---", e)


# --- Groq ---
from groq import Groq

client_groq = Groq(api_key=os.getenv("GROQ_API_KEY"))
resp_groq = client_groq.chat.completions.create(
    model="qwen/qwen3.6-27b",
    messages=[
        {
            "role": "user",
            "content": [
                {"type": "text", "text": EXTRACTION_PROMPT},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}}
            ]
        }
    ]
)
raw_groq = resp_groq.choices[0].message.content
print("\n--- GROQ RAW ---")
print(raw_groq)

try:
    parsed_groq = json.loads(clean_json_response(raw_groq))
    print("--- GROQ PARSED ---")
    print(parsed_groq)
except json.JSONDecodeError as e:
    print("--- GROQ PARSE FAILED ---", e)