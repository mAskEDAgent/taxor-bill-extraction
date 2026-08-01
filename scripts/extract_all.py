from dotenv import load_dotenv
import os
import json
import re
import base64
import glob
import time

load_dotenv()

from google import genai
from google.genai import types
from mistralai.client import Mistral
from groq import Groq

client_gemini = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))
client_mistral = Mistral(api_key=os.getenv("MISTRAL_API_KEY"))
client_groq = Groq(api_key=os.getenv("GROQ_API_KEY"))

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


def clean_json_response(raw_text):
    text = re.sub(r'<think>.*?</think>', '', raw_text, flags=re.DOTALL)
    text = text.strip()
    text = re.sub(r'^```(?:json)?\s*', '', text)
    text = re.sub(r'\s*```$', '', text)
    return text.strip()


def extract_gemini(image_bytes):
    resp = client_gemini.models.generate_content(
        model="gemini-3.6-flash",
        contents=[
            types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"),
            EXTRACTION_PROMPT
        ]
    )
    usage = {
        "input_tokens": resp.usage_metadata.prompt_token_count,
        "output_tokens": resp.usage_metadata.candidates_token_count,
    }
    return resp.text, usage


def extract_mistral(image_b64):
    resp = client_mistral.chat.complete(
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
    usage = {
        "input_tokens": resp.usage.prompt_tokens,
        "output_tokens": resp.usage.completion_tokens,
    }
    return resp.choices[0].message.content, usage


def extract_groq(image_b64):
    resp = client_groq.chat.completions.create(
        model="qwen/qwen3.6-27b",
        max_completion_tokens=4096,
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
    usage = {
        "input_tokens": resp.usage.prompt_tokens,
        "output_tokens": resp.usage.completion_tokens,
    }
    return resp.choices[0].message.content, usage


MODELS = {
    "gemini": extract_gemini,
    "mistral": extract_mistral,
    "groq": extract_groq,
}

os.makedirs("results/raw", exist_ok=True)

image_files = sorted(glob.glob("data/images/*.jpg"))
print(f"Found {len(image_files)} images")

for image_path in image_files:
    bill_id = os.path.splitext(os.path.basename(image_path))[0]

    with open(image_path, "rb") as f:
        image_bytes = f.read()
    image_b64 = base64.b64encode(image_bytes).decode("utf-8")

    for model_name, extract_fn in MODELS.items():
        out_path = f"results/raw/{model_name}_{bill_id}.json"

        if os.path.exists(out_path):
            with open(out_path) as f:
                existing = json.load(f)
            if existing.get("parse_success"):
                print(f"SKIP (already done): {out_path}")
                continue
            else:
                print(f"RETRYING (previous attempt failed): {out_path}")

        print(f"Extracting {bill_id} with {model_name}...")

        try:
            if model_name == "gemini":
                raw_response, usage = extract_fn(image_bytes)
            else:
                raw_response, usage = extract_fn(image_b64)

            cleaned = clean_json_response(raw_response)
            parsed = json.loads(cleaned)

            result = {
                "bill_id": bill_id,
                "model": model_name,
                "raw_response": raw_response,
                "parsed": parsed,
                "parse_success": True,
                "error": None,
                "usage": usage,
            }

        except Exception as e:
            result = {
                "bill_id": bill_id,
                "model": model_name,
                "raw_response": raw_response if 'raw_response' in dir() else None,
                "parsed": None,
                "parse_success": False,
                "error": str(e),
                "usage": None,
            }
            print(f"  FAILED: {e}")

        with open(out_path, "w") as f:
            json.dump(result, f, indent=2)

        time.sleep(1)

print("Done.")