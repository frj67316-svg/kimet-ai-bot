import os
import logging
import asyncio
import random
from flask import Flask, jsonify
import requests
from threading import Thread
import time

# Local imports for upload utilities
from utils.tiktok import upload_to_tiktok
from utils.youtube import upload_to_youtube

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
# Interval (seconds) for generating and publishing videos – default 4 hours (14400s).
GEN_INTERVAL = int(os.getenv('GEN_INTERVAL_SECONDS', 14400))

# Optional list of prompts (comma‑separated) – fallback to a small default list.
PROMPT_LIST = os.getenv("PROMPTS", "حقيقة غريبة,لغز غامض,معلومة مثيرة").split(",")

# ---------------------------------------------------------------------------
# Video generation models (same as before)
# ---------------------------------------------------------------------------
VIDEO_MODELS = [
    {
        "name": "Stable Video Diffusion (Stability AI)",
        "endpoint": "https://api-inference.huggingface.co/models/stabilityai/stable-video-diffusion",
        "input_key": "inputs",
        "output_key": "url",
    },
    {
        "name": "VideoCrafter (ByteDance)",
        "endpoint": "https://api-inference.huggingface.co/models/ByteDance/VideoCrafter",
        "input_key": "inputs",
        "output_key": "url",
    },
    {
        "name": "OpenVideo (HuggingFace Spaces)",
        "endpoint": "https://huggingface.co/spaces/fffiloni/StableVideoDiffusion/api/predict",
        "input_key": "data",
        "output_key": "video",
    },
]


def generate_video(prompt: str) -> str | None:
    """Generate a video from *prompt* using the first available model.
    Returns the local temporary path to the downloaded ``.mp4`` file or ``None`` on failure.
    """
    headers = {"Accept": "application/json"}
    for model in VIDEO_MODELS:
        endpoint = model["endpoint"]
        input_key = model.get("input_key", "inputs")
        output_key = model.get("output_key", "url")
        payload = {input_key: prompt}
        try:
            response = requests.post(endpoint, json=payload, headers=headers, timeout=30)
            response.raise_for_status()
            data = response.json()
            video_url = data.get(output_key)
            if video_url and video_url.lower().endswith('.mp4'):
                logging.info(f"Video generated via {model['name']} -> {video_url}")
                # download to a temporary file
                try:
                    vid_resp = requests.get(video_url, stream=True, timeout=30)
                    vid_resp.raise_for_status()
                    temp_path = os.path.join(os.getcwd(), "temp_video.mp4")
                    with open(temp_path, "wb") as f:
                        for chunk in vid_resp.iter_content(chunk_size=8192):
                            f.write(chunk)
                    return temp_path
                except Exception as dl_err:
                    logging.error(f"Failed to download video from {video_url}: {dl_err}")
                    return None
            else:
                logging.warning(f"Model {model['name']} did not return a .mp4 URL. Response: {data}")
        except Exception as e:
            logging.error(f"Error using model {model['name']}: {e}")
            continue
    return None


def pick_prompt() -> str:
    """Select a random prompt from ``PROMPT_LIST``.
    ``PROMPT_LIST`` can be overridden via the ``PROMPTS`` environment variable.
    """
    return random.choice(PROMPT_LIST).strip()

# ---------------------------------------------------------------------------
# Background worker – runs forever, generating and publishing videos.
# ---------------------------------------------------------------------------
async def video_worker():
    while True:
        prompt = pick_prompt()
        logging.info(f"Generating video for prompt: {prompt}")
        video_path = generate_video(prompt)
        if video_path:
            try:
                # Upload to TikTok
                if upload_to_tiktok(video_path):
                    logging.info("Video successfully uploaded to TikTok.")
                else:
                    logging.error("TikTok upload failed.")
                # Upload to YouTube Shorts
                if upload_to_youtube(video_path):
                    logging.info("Video successfully uploaded to YouTube Shorts.")
                else:
                    logging.error("YouTube upload failed.")
            finally:
                # Clean up temporary file
                try:
                    os.remove(video_path)
                    logging.info(f"Removed temporary video file {video_path}")
                except Exception as rm_err:
                    logging.warning(f"Could not delete temporary video file: {rm_err}")
        else:
            logging.error("Video generation failed for all models.")
        logging.info(f"Sleeping for {GEN_INTERVAL} seconds before next generation cycle.")
        await asyncio.sleep(GEN_INTERVAL)

# ---------------------------------------------------------------------------
# Flask web service (minimal) – provides health check.
# ---------------------------------------------------------------------------
app = Flask(__name__)

@app.route("/", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    # Start Flask in a daemon thread.
    # Self‑ping thread to keep Render awake (every 10 min).
    def self_ping():
        url = os.getenv("RENDER_EXTERNAL_URL")
        if not url:
            port = int(os.getenv("PORT", "8080"))
            url = f"http://127.0.0.1:{port}/"
        while True:
            try:
                requests.get(url, timeout=10)
                logging.info("Self‑ping succeeded")
            except Exception as e:
                logging.warning(f"Self‑ping failed: {e}")
            time.sleep(600)
    # Start self-ping thread
    Thread(target=self_ping, daemon=True).start()
    def run_flask():
        port = int(os.getenv("PORT", "8080"))
        app.run(host="0.0.0.0", port=port)
    Thread(target=run_flask, daemon=True).start()
    # Run the async video worker until the process is terminated.
    asyncio.run(video_worker())
