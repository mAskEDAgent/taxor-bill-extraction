from dotenv import load_dotenv, find_dotenv
import os

print("dotenv file found at:", find_dotenv())
load_dotenv()

print("GOOGLE_API_KEY:", repr(os.getenv("GOOGLE_API_KEY")))
print("MISTRAL_API_KEY:", repr(os.getenv("MISTRAL_API_KEY")))
print("GROQ_API_KEY:", repr(os.getenv("GROQ_API_KEY")))

# --- Gemini ---
from google import genai

client_gemini = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))
resp = client_gemini.models.generate_content(
    model="gemini-3.6-flash",
    contents="Say hello in one word."
)
print("Gemini:", resp.text)

# --- Mistral ---
from mistralai.client import Mistral

client_mistral = Mistral(api_key=os.getenv("MISTRAL_API_KEY"))
resp = client_mistral.chat.complete(
    model="pixtral-12b-2409",
    messages=[{"role": "user", "content": "Say hello in one word."}]
)
print("Mistral:", resp.choices[0].message.content)

# --- Groq ---
from groq import Groq

client_groq = Groq(api_key=os.getenv("GROQ_API_KEY"))
resp = client_groq.chat.completions.create(
    model="qwen/qwen3.6-27b",
    messages=[{"role": "user", "content": "Say hello in one word."}]
)
print("Groq:", resp.choices[0].message.content)