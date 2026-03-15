import os
from google import genai
from dotenv import load_dotenv

load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

MODEL = "gemini-2.0-flash"

try:
    response = client.models.generate_content(
        model=MODEL,
        contents="Output exactly this JSON and nothing else: {\"test\": \"success\"}"
        # No generation_config here — add if needed via config object below
    )
    print("Success! Raw response:")
    print(response.text)
except Exception as e:
    print("Failed:")
    print(str(e))