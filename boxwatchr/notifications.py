import requests
from datetime import datetime, timezone
from boxwatchr.logger import get_logger

logger = get_logger("boxwatchr.notifications")


def send_discord_notification(webhook_url, email_data, rule_name, spam_score=None, email_id=None, actions=None):
    """Send an enhanced Discord embed notification when a rule matches."""
    extra = {"email_id": email_id}

    # Use global webhook if per-rule webhook not provided
    if not webhook_url:
        from boxwatchr import config
        webhook_url = config.DISCORD_WEBHOOK_URL

    if not webhook_url:
        logger.warning("No Discord webhook URL configured (neither per-rule nor global)", extra=extra)
        return False

    sender = email_data.get("sender", "Unknown")
    subject = email_data.get("subject", "(no subject)")
    recipients = email_data.get("recipients", [])
    date_received = email_data.get("date_received", "")

    # Color based on spam score
    if spam_score is not None and spam_score >= 10:
        color = 0xCC0000  # Red - high spam
    elif spam_score is not None and spam_score >= 5:
        color = 0xFFAA00  # Orange - medium spam
    elif spam_score is not None and spam_score < 0:
        color = 0x00CC66  # Green - ham
    else:
        color = 0x5D9EE3  # Blue - default/low

    fields = [
        {"name": "📧 Sender", "value": sender[:256], "inline": True},
        {"name": "🏷️ Rule", "value": rule_name[:256], "inline": True},
    ]

    if spam_score is not None:
        score_emoji = "🟢" if spam_score < 2 else "🟡" if spam_score < 5 else "🟠" if spam_score < 10 else "🔴"
        fields.append({"name": "📊 Spam Score", "value": "%s %.2f" % (score_emoji, spam_score), "inline": True})

    if recipients:
        recipient_str = ", ".join(recipients[:3])
        if len(recipients) > 3:
            recipient_str += " (+%d more)" % (len(recipients) - 3)
        fields.append({"name": "📬 Recipients", "value": recipient_str[:256], "inline": False})

    if date_received:
        fields.append({"name": "📅 Received", "value": date_received, "inline": True})

    if actions:
        action_strs = []
        for a in actions:
            atype = a.get("type", "")
            if atype == "move":
                action_strs.append("📁 Move → %s" % a.get("destination", "?"))
            elif atype == "mark_read":
                action_strs.append("✅ Mark read")
            elif atype == "mark_unread":
                action_strs.append("📩 Mark unread")
            elif atype == "flag":
                action_strs.append("🚩 Flag")
            elif atype == "unflag":
                action_strs.append("🏳️ Unflag")
            elif atype == "learn_spam":
                action_strs.append("🚫 Learn spam")
            elif atype == "learn_ham":
                action_strs.append("✉️ Learn ham")
            elif atype == "add_label":
                action_strs.append("🏷️ Label: %s" % a.get("label", "?"))
        if action_strs:
            fields.append({"name": "⚡ Actions", "value": "\n".join(action_strs), "inline": False})

    # Truncate subject for title
    title_subject = subject[:200] + "…" if len(subject) > 200 else subject

    payload = {
        "embeds": [{
            "title": "📬 %s" % title_subject,
            "description": "Rule **%s** matched this email." % rule_name,
            "color": color,
            "fields": fields,
            "footer": {"text": "boxwatchr • email filtering daemon"},
            "timestamp": datetime.now(timezone.utc).isoformat(),
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
