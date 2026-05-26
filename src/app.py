import os
from fastapi import FastAPI, HTTPException
import httpx
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

HF_API_URL = "https://api-inference.huggingface.co/models/microsoft/DialoGPT-medium"
HF_TOKEN = os.getenv("HF_API_TOKEN")

if not HF_TOKEN:
    raise RuntimeError("HF_API_TOKEN environment variable not set")

headers = {"Authorization": f"Bearer {HF_TOKEN}"}

@app.post("/chat")
async def chat(message: dict):
    """Send a user message to the HuggingFace chat model and return the response.
    Expected JSON body: {"inputs": "your message"}
    """
    if "inputs" not in message:
        raise HTTPException(status_code=400, detail="'inputs' field required")
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(HF_API_URL, headers=headers, json={"inputs": message["inputs"]})
        response.raise_for_status()
        return response.json()
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=str(e))
