import os
import requests
from django.conf import settings

# FIXED: Reads BOTH settings.py AND env vars
GROQ_API_KEY = getattr(settings, "GROQ_API_KEY") or os.environ.get("GROQ_API_KEY")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

def ask_cybersecurity_bot(question: str) -> str:
    if not GROQ_API_KEY:
        return '{"error": "GROQ_API_KEY missing. Terminal: export GROQ_API_KEY=gsk_... (same terminal as runserver)"}'
    if not question.strip():
        return '{"error": "Empty question"}'
        
    payload = {
        "model": "llama-3.1-8b-instant",
        "messages": [
            {
                "role": "system", 
                "content": """You are a friendly cybersecurity tutor for ages <15 to >50. 
                Help with cybersecurity tasks. Provide accurate info & suggestions. 
                Short, informative answers with clear headings. Easy for teens/adults/elders.
                Include relevant resources, fun facts. Suggest other topics."""
            },
            {"role": "user", "content": question}
        ],
        "temperature": 0.3,
        "max_tokens": 1000,
    }

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
    }

    try:
        resp = requests.post(GROQ_URL, json=payload, headers=headers, timeout=15)
        if resp.status_code == 200:
            return resp.json()["choices"][0]["message"]["content"]
        return f"Groq API error {resp.status_code}: {resp.text[:200]}..."
    except requests.RequestException as e:
        return f"Network error: {str(e)}"