# Website Insights AI

Scrapes any website and shows its **services, purpose, contact info, social links and key pages**,
with a built-in **mini chatbot** that answers questions about the scraped site.

- Frontend: HTML, CSS, JavaScript
- Backend: Python (Flask, Requests, BeautifulSoup)
- Chatbot: OpenRouter AI (optional key) or built-in rule-based mode

## Run in VS Code
1. Open this folder in VS Code.
2. Open a terminal (Ctrl + `) and create a virtual environment:
   - Windows: `python -m venv venv` then `venv\Scripts\activate`
   - Mac/Linux: `python3 -m venv venv` then `source venv/bin/activate`
3. Install packages: `pip install -r requirements.txt`
4. (Optional) For AI chatbot answers: copy `.env.example` to `.env` and paste your OpenRouter key.
   Without it the chatbot still works in basic mode.
5. Start the server: `python app.py`
6. Open http://127.0.0.1:5000 in your browser, enter a website URL and click **Analyze**.
7. Click the 💬 button to chat about the website.

## Troubleshooting
- **"Empty reply" / "Python server not detected"** - the Python server is not running, or you opened the
  page another way (double-click or VS Code *Live Server*). Run `python app.py` and open
  **http://127.0.0.1:5000** (use that exact link).
- **Test scraping without the browser:** `python test_scraper.py https://www.python.org`
- **Windows shortcut:** double-click `run.bat` (installs packages and starts the app).
- Sites that need a login (student portals, dashboards) only show their public login page.

## Files
- `app.py` - Flask server and API routes (`/api/scrape`, `/api/chat`)
- `scraper.py` - scraping and data extraction logic
- `chatbot.py` - chatbot (OpenRouter + fallback)
- `test_scraper.py` - terminal test for the scraper
- `run.bat` / `run.sh` - one-click start scripts
- `static/` - `index.html`, `style.css`, `script.js`

## Notes
- Some sites (heavy JavaScript or bot protection) may return limited data.
- Scrape only sites you are allowed to, and respect their terms and robots.txt.
- Local/private addresses are blocked for safety.
