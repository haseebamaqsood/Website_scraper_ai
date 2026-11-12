"""
chatbot.py - Mini chatbot that answers questions about the scraped website.
Mode 1: OpenRouter AI (if OPENROUTER_API_KEY is set in .env)
Mode 2: built-in rule-based answers (works with no key at all)
"""
import os
import re

import requests

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


def build_context(data: dict) -> str:
    c = data.get("contact", {})
    lines = [
        f"Website: {data.get('site_name')} ({data.get('url')})",
        f"Title: {data.get('title')}",
        f"Description: {data.get('description')}",
        f"Purpose: {data.get('purpose')}",
        "Services/Products: " + "; ".join(data.get("services", [])),
        "Emails: " + ", ".join(c.get("emails", [])),
        "Phones: " + ", ".join(c.get("phones", [])),
        f"Address: {c.get('address')}",
        "Social links: " + ", ".join(f"{k}: {v}" for k, v in data.get("social_links", {}).items()),
        "Main headings: " + "; ".join(data.get("headings", {}).get("h2", [])),
        "Page text excerpt: " + data.get("text_excerpt", "")[:3500],
    ]
    return "\n".join(lines)


def ai_answer(question: str, data: dict, history: list):
    key = os.getenv("OPENROUTER_API_KEY", "").strip()
    if not key or key.startswith("your_"):
        return None
    system = (
        "You are a friendly assistant embedded in a website-insights tool. "
        "Answer ONLY using the scraped website information below. "
        "If the answer is not in the data, say you could not find it on the scraped pages. "
        "Keep answers short and clear.\n\n" + build_context(data)
    )
    messages = [{"role": "system", "content": system}]
    for m in history[-6:]:
        if m.get("role") in ("user", "assistant") and m.get("content"):
            messages.append({"role": m["role"], "content": str(m["content"])[:1000]})
    messages.append({"role": "user", "content": question})
    try:
        r = requests.post(
            OPENROUTER_URL,
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={"model": os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini"),
                  "messages": messages, "max_tokens": 400},
            timeout=30,
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"].strip()
    except Exception:
        return None  # fall back to rule-based answer


def rule_answer(question: str, data: dict) -> str:
    q = question.lower()
    c = data.get("contact", {})
    name = data.get("site_name", "this website")

    def has(*words):
        return any(w in q for w in words)

    if has("hello", "hi ", "hey") and len(q) < 20:
        return f"Hello! Ask me anything about {name} - services, purpose or contact details."
    if has("email", "mail"):
        return ("Email: " + ", ".join(c["emails"])) if c.get("emails") else \
            "I could not find an email address on the scraped pages."
    if has("phone", "call", "number", "whatsapp"):
        return ("Phone: " + ", ".join(c["phones"])) if c.get("phones") else \
            "I could not find a phone number on the scraped pages."
    if has("address", "location", "where", "office"):
        return f"Address: {c['address']}" if c.get("address") else \
            "No address was found on the scraped pages."
    if has("contact", "reach", "support"):
        parts = []
        if c.get("emails"): parts.append("Email: " + ", ".join(c["emails"]))
        if c.get("phones"): parts.append("Phone: " + ", ".join(c["phones"]))
        if c.get("contact_page"): parts.append("Contact page: " + c["contact_page"])
        return " | ".join(parts) or "No contact details were found on the scraped pages."
    if has("service", "offer", "product", "feature", "provide", "what do"):
        sv = data.get("services", [])
        return (f"{name} offers: " + "; ".join(sv[:10])) if sv else \
            "I could not detect specific services on the scraped pages."
    if has("purpose", "about", "mission", "what is", "who", "goal"):
        return data.get("purpose") or data.get("description") or "No purpose statement was found."
    if has("social", "twitter", "facebook", "linkedin", "instagram", "youtube", "github"):
        s = data.get("social_links", {})
        return "; ".join(f"{k}: {v}" for k, v in s.items()) or "No social links were found."

    # Fallback: find the sentence in page text that best matches the question
    words = {w for w in re.findall(r"[a-z]{4,}", q)}
    best, score = "", 0
    for sent in re.split(r"(?<=[.!?])\s+", data.get("text_excerpt", "")):
        sc = sum(1 for w in words if w in sent.lower())
        if sc > score:
            best, score = sent, sc
    if best and score:
        return best[:400]
    return ("I'm not sure about that. Try asking about the website's services, purpose, "
            "contact details or social links.")


def answer(question: str, data: dict, history=None) -> dict:
    history = history or []
    ai = ai_answer(question, data, history)
    if ai:
        return {"reply": ai, "mode": "ai"}
    return {"reply": rule_answer(question, data), "mode": "basic"}
