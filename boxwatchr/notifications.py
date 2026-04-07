import requests
from boxwatchr.logger import get_logger

logger = get_logger("boxwatchr.notifications")


def send_discord_notification(webhook_url, email_data, rule_name, spam_score=None, email_id=None):
    """Send a Discord embed notification when a rule matches."""
    extra = {"email_id": email_id}

    sender = email_data.get("sender", "Unknown")
    subject = email_data.get("subject", "(no subject)")

    fields = [
        {"name": "Sender", "value": sender, "inline": True},
        {"name": "Rule", "value": rule_name, "inline": True},
    ]

    if spam_score is not None:
        fields.append({"name": "Spam Score", "value": "%.2f" % spam_score, "inline": True})

    if spam_score is not None and spam_score >= 10:
        color = 0xCC0000
    elif spam_score is not None and spam_score >= 5:
        color = 0xFFAA00
    else:
        color = 0x5D9EE3

    payload = {
        "embeds": [{
            "title": "\U0001f4ec Rule Matched: %s" % rule_name,
            "description": subject,
            "color": color,
            "fields": fields,
            "footer": {"text": "boxwatchr"},
        }]
    }

    try:
        response = requests.post(
            webhook_url,
            json=payload,
            timeout=10,
            headers={"Content-Type": "application/json"},
        )
        if response.status_code in (200, 204):
            logger.info("Discord notification sent for rule '%s'", rule_name, extra=extra)
            return True
        else:
            logger.warning(
                "Discord webhook returned status %s: %s",
                response.status_code, response.text[:200],
                extra=extra,
            )
            return False
    except requests.exceptions.Timeout:
        logger.error("Discord webhook timed out", extra=extra)
        return False
    except requests.exceptions.ConnectionError:
        logger.error("Could not connect to Discord webhook", extra=extra)
        return False
    except Exception as e:
        logger.error("Discord notification failed: %s", e, extra=extra)
        return False
