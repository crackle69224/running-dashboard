import json
import os
import urllib.request

RESEND_API_KEY = os.environ.get("RESEND_API_KEY")
RESEND_FROM = os.environ.get("RESEND_FROM", "RunDash <onboarding@resend.dev>")


def send_email(to: str, subject: str, body: str) -> None:
    if not RESEND_API_KEY:
        # No email API configured (e.g. local dev) — log instead of sending.
        print(f"[email not configured] To: {to}\nSubject: {subject}\n{body}")
        return

    payload = json.dumps({
        "from": RESEND_FROM,
        "to": [to],
        "subject": subject,
        "text": body,
    }).encode()

    request = urllib.request.Request(
        "https://api.resend.com/emails",
        data=payload,
        method="POST",
        headers={
            "Authorization": f"Bearer {RESEND_API_KEY}",
            "Content-Type": "application/json",
            "User-Agent": "RunDash/1.0",
        },
    )
    with urllib.request.urlopen(request, timeout=15) as resp:
        if resp.status >= 300:
            raise RuntimeError(f"Resend API returned {resp.status}: {resp.read()}")
