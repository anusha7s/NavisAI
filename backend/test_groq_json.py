import os
from dotenv import load_dotenv
from groq import Groq

load_dotenv()
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

try:
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": "You MUST respond with ONLY a valid JSON object"},
            {"role": "user", "content": "test"}
        ],
        temperature=0.1,
        max_tokens=300,
        response_format={"type": "json_object"}
    )
    print("SUCCESS")
    print(response.choices[0].message.content)
except Exception as e:
    print("FAILED EXCEPTION:")
    print(str(e))
    import traceback
    traceback.print_exc()
