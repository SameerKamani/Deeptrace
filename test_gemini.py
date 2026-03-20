import httpx
import os
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

def test_model(model_name):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent"
    payload = {
        "contents": [{"parts": [{"text": "Hello, are you there?"}]}]
    }
    response = httpx.post(url, params={"key": api_key}, json=payload)
    print(f"Testing {model_name}... Status: {response.status_code}")
    if response.status_code != 200:
        print(response.text)
    else:
        print("Success!")

test_model("gemini-3.1-pro-preview")
test_model("gemini-3-flash-preview")
test_model("gemini-1.5-pro-latest")
