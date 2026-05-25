import os
import logging
from flask import Flask, request, abort
import requests
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters

# ---------------------------------------------------------------------------
# Configuration (read from environment variables)
# ---------------------------------------------------------------------------
TELEGRAM_TOKEN = "8857728669:AAFEnIedcN_IEx4CJbxJQPpow3T6ZUQjyeI"
RENDER_EXTERNAL_URL = os.getenv("RENDER_EXTERNAL_URL")  # e.g. https://my-bot.onrender.com

if not TELEGRAM_TOKEN or not RENDER_EXTERNAL_URL:
    raise RuntimeError("Missing required environment variables: TELEGRAM_TOKEN and/or RENDER_EXTERNAL_URL")

# ---------------------------------------------------------------------------
# List of public free video generation endpoints (no auth required)
# Each entry should point to an inference endpoint that accepts a JSON payload
# with a "prompt" (or "inputs") field and returns a JSON response containing a
# direct .mp4 URL under the key "url" (the exact key may differ â€“ see fallback).
# ---------------------------------------------------------------------------
VIDEO_MODELS = [
    {
        "name": "Stable Video Diffusion (Stability AI)",
        "endpoint": "https://api-inference.huggingface.co/models/stabilityai/stable-video-diffusion",
        "input_key": "inputs",   # key expected by the API for the prompt
        "output_key": "url"
    },
    {
        "name": "VideoCrafter (ByteDance)",
        "endpoint": "https://api-inference.huggingface.co/models/ByteDance/VideoCrafter",
        "input_key": "inputs",
        "output_key": "url"
    },
    {
        "name": "OpenVideo (HuggingFace Spaces)",
        "endpoint": "https://huggingface.co/spaces/fffiloni/StableVideoDiffusion/api/predict",
        "input_key": "data",
        "output_key": "video"  # Spaces often return {"video": "https://...mp4"}
    }
]

# ---------------------------------------------------------------------------
# Helper: request video generation with fallback logic
# ---------------------------------------------------------------------------
def generate_video(prompt: str) -> str | None:
    """Try each model in VIDEO_MODELS until one returns a usable .mp4 URL.
    Returns the URL string on success or None if all fail.
    """
    headers = {"Accept": "application/json"}
    payload_template = {"prompt": prompt}

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
                return video_url
            else:
                logging.warning(f"Model {model['name']} did not return a .mp4 URL. Response: {data}")
        except Exception as e:
            logging.error(f"Error using model {model['name']}: {e}")
            continue
    return None

# ---------------------------------------------------------------------------
# Telegram bot handlers
# ---------------------------------------------------------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "ط£ظ‡ظ„ط§ظ‹! ط£ط±ط³ظ„ ظ„ظٹ ط£ظٹ ظ†طµ ظˆط³ط£ظˆظ„ظ‘ط¯ ظ„ظƒ ظپظٹط¯ظٹظˆ ط¨ط§ط³طھط®ط¯ط§ظ… ظ†ظ…ط§ط°ط¬ ظ…ط¬ط§ظ†ظٹط© ظ…طھط§ط­ط© ط¹ط¨ط± ط§ظ„ط¥ظ†طھط±ظ†طھ."
    )

async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    prompt = update.message.text.strip()
    await update.message.reply_text("ط¬ط§ط±ظٹ طھظˆظ„ظٹط¯ ط§ظ„ظپظٹط¯ظٹظˆâ€¦ ظ‚ط¯ ظٹط³طھط؛ط±ظ‚ ط¹ط¯ط© ط«ظˆط§ظ†ظچ.")
    video_url = generate_video(prompt)
    if video_url:
        # Telegram can send a video by URL directly; it streams without storing the file.
        try:
            await update.message.reply_video(video_url, caption="ظ‡ط§ ظ‡ظˆ ط§ظ„ظپظٹط¯ظٹظˆ ط§ظ„ط®ط§طµ ط¨ظƒ!")
        except Exception as e:
            logging.error(f"Failed to send video via URL: {e}")
            await update.message.reply_text("ظپط´ظ„ ط¥ط±ط³ط§ظ„ ط§ظ„ظپظٹط¯ظٹظˆ. ط­ط§ظˆظ„ ظ…ط±ط© ط£ط®ط±ظ‰ ظ„ط§ط­ظ‚ط§ظ‹.")
    else:
        await update.message.reply_text(
            "ط¹ط°ط±ط§ظ‹طŒ ظ„ظ… ظ†طھظ…ظƒظ† ظ…ظ† طھظˆظ„ظٹط¯ ط§ظ„ظپظٹط¯ظٹظˆ ظ…ظ† ط£ظٹظچ ظ…ظ† ط§ظ„ظ†ظ…ط§ط°ط¬ ط§ظ„ظ…طھط§ط­ط© ط­ط§ظ„ظٹط§ظ‹."
        )

# ---------------------------------------------------------------------------
# Flask app that receives webhook POSTs from Telegram
# ---------------------------------------------------------------------------
app = Flask(__name__)

@app.route("/webhook", methods=["POST"])
def webhook():
    if request.method == "POST":
        update = Update.de_json(request.get_json(force=True), bot)
        # Dispatch update to PTB Application (runs async handlers)
        asyncio.run(application.process_update(update))
        return "OK", 200
    else:
        abort(400)

# ---------------------------------------------------------------------------
# Main entry point â€“ set webhook and start Flask server
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import asyncio
    # Build PTB application
    application = (
        ApplicationBuilder()
        .token(TELEGRAM_TOKEN)
        .post_init(lambda app: logging.basicConfig(level=logging.INFO))
        .build()
    )
    # Register handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))

    # Set webhook â€“ Render will expose the Flask app at RENDER_EXTERNAL_URL
    webhook_url = f"{RENDER_EXTERNAL_URL.rstrip('/')}/webhook"
    # `bot` is created lazily by PTB; we need a reference for the Flask route.
    bot = application.bot
    bot.set_webhook(url=webhook_url)
    logging.info(f"Webhook set to {webhook_url}")

    # Run Flask (Render expects the app to listen on the PORT env var)
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
