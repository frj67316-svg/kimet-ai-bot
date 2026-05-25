import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import logging
from flask import Flask, request, jsonify, abort
from utils.tiktok import TikTokUploader
from utils.youtube import YouTubeUploader
from utils.cookie_manager import CookieManager

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# Flask app
app = Flask(__name__)

# Initialize uploaders
cookie_manager = CookieManager()
tiktok_uploader = TikTokUploader(cookie_manager)
youtube_uploader = YouTubeUploader(cookie_manager)

@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint for Render"""
    return jsonify({"status": "healthy"}), 200

@app.route("/upload", methods=["POST"])
def upload_video():
    """Main endpoint for video upload"""
    try:
        data = request.get_json()
        platform = data.get("platform")
        video_path = data.get("video_path")
        title = data.get("title")
        description = data.get("description", "")
        
        if not all([platform, video_path, title]):
            return jsonify({"error": "Missing required fields"}), 400
        
        if platform.lower() == "tiktok":
            result = tiktok_uploader.upload(video_path, title, description)
        elif platform.lower() == "youtube":
            result = youtube_uploader.upload(video_path, title, description)
        else:
            return jsonify({"error": "Unsupported platform"}), 400
        
        return jsonify(result), 200
        
    except Exception as e:
        logger.error(f"Upload failed: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route("/status", methods=["GET"])
def status():
    """Check service status"""
    return jsonify({
        "status": "running",
        "endpoints": ["/health", "/upload", "/status"],
        "platforms": ["tiktok", "youtube"]
    }), 200

if __name__ == "__main__":
    # Run Flask server
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)