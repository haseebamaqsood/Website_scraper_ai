"""
app.py - Flask backend for the Website Insights AI tool.
Run:  python app.py   then open http://127.0.0.1:5000
"""
import os

from dotenv import load_dotenv
from flask import Flask, jsonify, request, send_from_directory

import chatbot
from scraper import ScrapeError, scrape_website

load_dotenv()
app = Flask(__name__, static_folder="static", static_url_path="")
CACHE = {}  # url -> scraped data (simple in-memory cache)


@app.route("/")
def home():
    return send_from_directory("static", "index.html")


@app.route("/api/health")
def api_health():
    key = os.getenv("OPENROUTER_API_KEY", "").strip()
    return jsonify({"status": "ok", "ai_chatbot": bool(key) and not key.startswith("your_")})


@app.route("/api/scrape", methods=["POST"])
def api_scrape():
    body = request.get_json(silent=True) or {}
    try:
        data = scrape_website(body.get("url", ""))
    except ScrapeError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:  # unexpected parsing problem
        app.logger.exception("Scrape failed")
        return jsonify({"error": f"Unexpected error: {e.__class__.__name__}: {e}"}), 500
    CACHE[data["url"]] = data
    return jsonify(data)


@app.route("/api/chat", methods=["POST"])
def api_chat():
    body = request.get_json(silent=True) or {}
    question = (body.get("message") or "").strip()
    url = body.get("url", "")
    if not question:
        return jsonify({"error": "Empty message."}), 400
    data = CACHE.get(url)
    if not data:
        return jsonify({"error": "Please scrape a website first."}), 400
    return jsonify(chatbot.answer(question[:500], data, body.get("history", [])))


@app.after_request
def add_cors(resp):
    """Lets index.html work even if it is opened directly from disk."""
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
    resp.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    return resp


@app.errorhandler(Exception)
def handle_any_error(e):
    """Make sure the browser ALWAYS receives JSON, never an empty/HTML reply."""
    app.logger.exception("Unhandled error")
    return jsonify({"error": f"Server error: {e.__class__.__name__}"}), 500


if __name__ == "__main__":
    # use_reloader=False prevents the server restarting mid-request (empty response)
    port = int(os.getenv("PORT", 5000))
    print(f"\n  Website Insights AI is running.\n  Open this link in your browser:  http://127.0.0.1:{port}\n")
    app.run(debug=False, use_reloader=False, threaded=True, port=port)
