import os
import logging
import asyncio
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
# ---------------------------------------------------------------------------
VIDEO_MODELS = [
    {
        "name": "Stable Video Diffusion (Stability AI)",
        "endpoint": "https://api-inference.huggingface.co/models/stabilityai/stable-video-diffusion",
        "input_key": "inputs",
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
        "output_key": "video"
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
        "أهلاً! أرسل لي أي نص وسأولّد لك فيديو باستخدام نماذج مجانية متاحة عبر الإنترنت."
    )

async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    prompt = update.message.text.strip()
    await update.message.reply_text("جاري توليد الفيديو… قد يستغرق عدة ثوانٍ.")
    video_url = generate_video(prompt)
    if video_url:
        try:
            await update.message.reply_video(video_url, caption="ها هو الفيديو الخاص بك!")
        except Exception as e:
            logging.error(f"Failed to send video via URL: {e}")
            await update.message.reply_text("فشل إرسال الفيديو. حاول مرة أخرى لاحقاً.")
    else:
        await update.message.reply_text(
            "عذراً، لم نتمكن من توليد الفيديو من أيٍ من النماذج المتاحة حالياً."
        )

# ---------------------------------------------------------------------------
# Build the PTB application and register handlers (global, before Flask routes)
# ---------------------------------------------------------------------------
application = (
    ApplicationBuilder()
    .token(TELEGRAM_TOKEN)
    .post_init(lambda app: logging.basicConfig(level=logging.INFO))
    .build()
)
application.add_handler(CommandHandler("start", start))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
bot = application.bot

# ---------------------------------------------------------------------------
# Flask app that receives webhook POSTs from Telegram
# ---------------------------------------------------------------------------
app = Flask(__name__)

# Health check endpoint
@app.route('/', methods=['GET'])
def health():
    return "Bot is running", 200


@app.route("/webhook", methods=["POST"])
def webhook():
    if request.method == "POST":
        update = Update.de_json(request.get_json(force=True), application.bot)
        # Schedule asynchronous processing without blocking the Flask request
        asyncio.create_task(application.process_update(update))
        return "OK", 200
    else:
        abort(400)

# ---------------------------------------------------------------------------
# Main entry point – set webhook and start Flask server
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import asyncio
    async def start():
        # Set webhook – Render will expose the Flask app at RENDER_EXTERNAL_URL
        webhook_url = f"{RENDER_EXTERNAL_URL.rstrip('/')}/webhook"
        if webhook_url.lower().startswith('https://'):
            try:
                await application.bot.set_webhook(url=webhook_url)
                logging.info(f"Webhook set to {webhook_url}")
            except Exception as e:
                logging.error(f"Failed to set webhook: {e}")
        else:
            logging.warning("Webhook URL is not HTTPS; skipping webhook registration for local testing.")
        # Run Flask (Render expects the app to listen on the PORT env var)
        port = int(os.getenv("PORT", 8080))
        app.run(host="0.0.0.0", port=port)
    asyncio.run(start())
