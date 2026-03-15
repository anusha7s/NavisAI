import os
import time
from dotenv import load_dotenv
from groq import Groq

load_dotenv()
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

print("Testing Groq connection...")
start = time.time()
try:
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": "Say hello world"}],
        max_tokens=10
    )
    print(f"Success! Response in {time.time()-start:.2f}s:")
    print(response.choices[0].message.content)
except Exception as e:
    print(f"Failed after {time.time()-start:.2f}s:")
    print(str(e))
