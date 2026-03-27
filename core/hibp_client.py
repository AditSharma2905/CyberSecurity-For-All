import requests
from django.conf import settings

BASE_URL = "https://haveibeenpwned.com/api/v3/breachedaccount/"

def check_breaches(email: str):
    if not email:
        return []

    api_key = getattr(settings, "HIBP_API_KEY", None)
    if not api_key:
        return None

    headers = {
        "hibp-api-key": api_key,
        "user-agent": "CyberSecurityForAll/1.0",
    }
    params = {"truncateResponse": "false"}

    try:
        resp = requests.get(BASE_URL + email, headers=headers, params=params, timeout=5)
    except requests.RequestException:
        return None

    if resp.status_code == 404:
        return []        # no breaches
    if resp.status_code == 200:
        return resp.json()
    return None