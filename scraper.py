"""
scraper.py - Website scraping logic.
Extracts: name, purpose, services, contact info (emails, phones, address),
social links, key pages and headings from a website.
"""
import ipaddress
import os
import re
import socket
import time
from urllib.parse import urljoin, urlparse

import requests
import urllib3
from bs4 import BeautifulSoup

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; WebsiteInsightBot/1.0; educational project)",
    "Accept-Language": "en-US,en;q=0.9",
}
TIMEOUT = 12
MAX_BYTES = 2_500_000

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
PHONE_RE = re.compile(r"(?:\+?\d{1,3}[\s\-.]?)?(?:\(?\d{2,4}\)?[\s\-.]?)\d{3,4}[\s\-.]?\d{3,4}")
BAD_EMAIL_END = (".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".css", ".js")

SERVICE_WORDS = ("service", "solution", "product", "feature", "pricing", "platform",
                 "offering", "what we do", "capabilit", "plans", "tools", "enterprise")
ABOUT_WORDS = ("about", "company", "mission", "who we are", "our story", "why")
CONTACT_WORDS = ("contact", "support", "reach us", "get in touch", "help")
SOCIALS = {
    "facebook.com": "Facebook", "twitter.com": "Twitter/X", "x.com": "Twitter/X",
    "linkedin.com": "LinkedIn", "instagram.com": "Instagram", "youtube.com": "YouTube",
    "github.com": "GitHub", "tiktok.com": "TikTok", "t.me": "Telegram",
    "wa.me": "WhatsApp", "pinterest.com": "Pinterest",
}


class ScrapeError(Exception):
    pass


def normalize_url(url: str) -> str:
    url = (url or "").strip()
    if not url:
        raise ScrapeError("Please enter a website URL.")
    if not re.match(r"^https?://", url, re.I):
        url = "https://" + url
    parsed = urlparse(url)
    if not parsed.netloc or "." not in parsed.netloc and parsed.hostname != "localhost":
        raise ScrapeError("That does not look like a valid website address.")
    return url


def _check_safe_host(url: str):
    """Block localhost/private addresses so the tool cannot be abused (SSRF)."""
    if os.getenv("ALLOW_PRIVATE_HOSTS") == "1":
        return
    host = urlparse(url).hostname
    try:
        for info in socket.getaddrinfo(host, None):
            ip = ipaddress.ip_address(info[4][0])
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                raise ScrapeError("Private or local addresses are not allowed.")
    except socket.gaierror:
        raise ScrapeError(f"Could not resolve '{host}'. Check the address.")


def fetch(url: str):
    """Download a page safely. Always raises ScrapeError (never anything else)."""
    _check_safe_host(url)
    session = requests.Session()
    session.headers.update(HEADERS)
    insecure = False
    try:
        try:
            r = session.get(url, timeout=(6, 12), stream=True, allow_redirects=True)
        except requests.exceptions.SSLError:
            # Many government/university sites have incomplete certificate chains.
            # Retry once without certificate verification (read-only scraping).
            insecure = True
            r = session.get(url, timeout=(6, 12), stream=True, allow_redirects=True, verify=False)
        if r.status_code >= 400:
            raise ScrapeError(f"The website returned HTTP {r.status_code}.")
        ctype = r.headers.get("Content-Type", "").lower()
        if ctype and "html" not in ctype and "xml" not in ctype:
            raise ScrapeError("The URL did not return an HTML page.")
        chunks, size = [], 0
        for chunk in r.iter_content(chunk_size=65536):
            chunks.append(chunk)
            size += len(chunk)
            if size >= MAX_BYTES:
                break
        content = b"".join(chunks)
        if not content.strip():
            raise ScrapeError("The website returned an empty page.")
        encoding = r.encoding if r.encoding and "iso-8859" not in r.encoding.lower() else None
        text = content.decode(encoding or "utf-8", errors="replace")
        return text, r.url
    except ScrapeError:
        raise
    except requests.exceptions.Timeout:
        raise ScrapeError("The website took too long to respond.")
    except requests.exceptions.ConnectionError:
        raise ScrapeError("Could not connect to the website. Check the link and your internet.")
    except Exception as e:  # urllib3 / decoding / anything unexpected
        raise ScrapeError(f"Could not read the website ({e.__class__.__name__}).")
    finally:
        session.close()


def clean(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _meta(soup, *names):
    for n in names:
        tag = soup.find("meta", attrs={"name": n}) or soup.find("meta", attrs={"property": n})
        if tag and tag.get("content"):
            return clean(tag["content"])
    return ""


def _emails(soup, text):
    found = set()
    for a in soup.select('a[href^="mailto:"]'):
        addr = a["href"][7:].split("?")[0].strip()
        if addr:
            found.add(addr.lower())
    for m in EMAIL_RE.findall(text):
        if not m.lower().endswith(BAD_EMAIL_END):
            found.add(m.lower())
    return sorted(found)


def _phones(soup, text):
    found = []
    for a in soup.select('a[href^="tel:"]'):
        num = clean(a["href"][4:])
        if num and num not in found:
            found.append(num)
    for m in PHONE_RE.findall(text):
        digits = re.sub(r"\D", "", m)
        if 9 <= len(digits) <= 14 and (m.strip().startswith("+") or re.search(r"[\s\-.()]", m.strip())):
            m = clean(m)
            if m not in found:
                found.append(m)
    return found[:6]


def _address(soup):
    tag = soup.find("address")
    if tag:
        return clean(tag.get_text(" "))[:250]
    for el in soup.select('[itemprop="address"], [class*="address"], [id*="address"]'):
        t = clean(el.get_text(" "))
        if 10 < len(t) < 250:
            return t
    return ""


def _socials(soup):
    out = {}
    for a in soup.find_all("a", href=True):
        href = a["href"]
        host = urlparse(href).netloc.lower().replace("www.", "")
        for dom, name in SOCIALS.items():
            if host == dom or host.endswith("." + dom):
                out.setdefault(name, href)
    return out


def _headings(soup, level):
    seen, out = set(), []
    for h in soup.find_all(level):
        t = clean(h.get_text(" "))
        if 3 < len(t) < 120 and t.lower() not in seen:
            seen.add(t.lower())
            out.append(t)
    return out


def _services(soup):
    """Collect likely service/product names from nav links, headings and lists."""
    items, seen = [], set()

    def add(t):
        t = clean(t)
        k = t.lower()
        if 3 < len(t) < 90 and k not in seen:
            seen.add(k)
            items.append(t)

    # 1) Links whose text/href look like services/products
    for a in soup.find_all("a", href=True):
        txt = clean(a.get_text(" "))
        if any(w in (txt + " " + a["href"]).lower() for w in SERVICE_WORDS) and len(txt) < 60:
            add(txt)
    # 2) Headings that sit inside sections mentioning services
    for sec in soup.find_all(["section", "div"], id=True):
        if any(w in sec.get("id", "").lower() for w in SERVICE_WORDS):
            for h in sec.find_all(["h2", "h3", "h4"]):
                add(h.get_text(" "))
    # 3) Fallback: h2 / h3 headings
    if len(items) < 4:
        for h in soup.find_all(["h2", "h3"]):
            add(h.get_text(" "))
    return items[:15]


def _purpose(soup, description):
    parts = []
    if description:
        parts.append(description)
    for p in soup.find_all("p"):
        t = clean(p.get_text(" "))
        if len(t) > 70 and t not in parts:
            parts.append(t)
        if len(parts) >= 3:
            break
    return " ".join(parts)[:700]


def _find_pages(soup, base_url):
    """Locate About / Contact / Services pages on the same domain."""
    base_host = urlparse(base_url).netloc
    pages = {"about": None, "contact": None, "services": None}
    for a in soup.find_all("a", href=True):
        href = urljoin(base_url, a["href"]).split("#")[0]
        if urlparse(href).netloc != base_host:
            continue
        label = (clean(a.get_text(" ")) + " " + href).lower()
        for key, words in (("about", ABOUT_WORDS), ("contact", CONTACT_WORDS), ("services", SERVICE_WORDS)):
            if pages[key] is None and any(w in label for w in words):
                pages[key] = href
    return pages


def _extract_page(html, url):
    try:
        soup = BeautifulSoup(html, "lxml")
    except Exception:  # lxml missing/broken -> use Python's built-in parser
        soup = BeautifulSoup(html, "html.parser")
    for t in soup(["script", "style", "noscript", "svg"]):
        t.decompose()
    text = clean(soup.get_text(" "))
    desc = _meta(soup, "description", "og:description", "twitter:description")
    return soup, text, desc


def scrape_website(raw_url: str) -> dict:
    started = time.time()
    url = normalize_url(raw_url)
    html, final_url = fetch(url)
    soup, text, desc = _extract_page(html, final_url)
    pages = _find_pages(soup, final_url)

    title = clean(soup.title.get_text()) if soup.title else ""
    site_name = _meta(soup, "og:site_name") or title.split("|")[0].split(" - ")[0].strip() \
        or urlparse(final_url).netloc

    emails = _emails(soup, text)
    phones = _phones(soup, text)
    address = _address(soup)
    socials = _socials(soup)
    services = _services(soup)
    purpose = _purpose(soup, desc)
    about_text = ""

    # Visit up to 3 extra pages (about, contact, services) for richer data
    for key in ("about", "contact", "services"):
        link = pages.get(key)
        if not link or link == final_url or time.time() - started > 25:
            continue
        try:
            h2, u2 = fetch(link)
            s2, t2, d2 = _extract_page(h2, u2)
        except Exception:
            continue
        if key == "about":
            about_text = _purpose(s2, d2)
        if key == "contact":
            emails = sorted(set(emails) | set(_emails(s2, t2)))
            phones = list(dict.fromkeys(phones + _phones(s2, t2)))[:6]
            address = address or _address(s2)
        if key == "services":
            for sv in _services(s2):
                if sv.lower() not in [x.lower() for x in services]:
                    services.append(sv)
        socials = {**_socials(s2), **socials}

    return {
        "url": final_url,
        "site_name": site_name,
        "title": title,
        "description": desc,
        "purpose": about_text or purpose,
        "services": services[:20],
        "contact": {
            "emails": emails[:8],
            "phones": phones,
            "address": address,
            "contact_page": pages.get("contact") or "",
        },
        "social_links": socials,
        "key_pages": {k: v for k, v in pages.items() if v},
        "headings": {"h1": _headings(soup, "h1")[:5], "h2": _headings(soup, "h2")[:10]},
        "word_count": len(text.split()),
        "text_excerpt": text[:6000],
    }
