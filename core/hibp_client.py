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
        response = requests.get(
            f"{BASE_URL}{email}",
            headers=headers,
            params=params,
            timeout=5
        )

        if response.status_code == 200:
            return response.json()
        if response.status_code == 404:
            return []

    except requests.RequestException:
        pass

    return None
