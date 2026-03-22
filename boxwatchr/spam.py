import requests
from boxwatchr import config
from boxwatchr.logger import get_logger

logger = get_logger("boxwatchr.spam")

def check(raw_message, email_id=None):
    url = f"http://{config.RSPAMD_HOST}:{config.RSPAMD_PORT}/checkv2"
    logger.debug("Submitting message to rspamd at %s", url, extra={"email_id": email_id})

    try:
        response = requests.post(
            url,
            data=raw_message,
            headers={"Content-Type": "text/plain"},
            timeout=10
        )

        if response.status_code != 200:
            logger.error(
                "rspamd returned status %s: %s",
                response.status_code,
                response.text,
                extra={"email_id": email_id}
            )
            return None

        result = response.json()

        score = result.get("score", 0.0)
        action = result.get("action", "unknown")
        symbols = result.get("symbols", {})

        logger.debug(
            "rspamd score: %.2f, action: %s, symbols fired: %s",
            score,
            action,
            len(symbols),
            extra={"email_id": email_id}
        )

        if symbols:
            for symbol, details in symbols.items():
                symbol_score = details.get("score", 0.0)
                logger.debug(
                    "Symbol: %s (score: %.2f)",
                    symbol,
                    symbol_score,
                    extra={"email_id": email_id}
                )

        if score >= config.SPAM_THRESHOLD:
            logger.debug(
                "Message score %.2f exceeds threshold %.2f, action: %s",
                score,
                config.SPAM_THRESHOLD,
                config.SPAM_ACTION,
                extra={"email_id": email_id}
            )
        else:
            logger.debug(
                "Message score %.2f is below threshold %.2f, no spam action taken",
                score,
                config.SPAM_THRESHOLD,
                extra={"email_id": email_id}
            )

        return {
            "score": score,
            "action": action,
            "symbols": symbols,
            "is_spam": score >= config.SPAM_THRESHOLD
        }

    except requests.exceptions.Timeout:
        logger.error("rspamd request timed out", extra={"email_id": email_id})
        return None

    except requests.exceptions.ConnectionError:
        logger.error("Could not connect to rspamd at %s", url, extra={"email_id": email_id})
        return None

    except Exception as e:
        logger.error("Unexpected error during spam check: %s", e, extra={"email_id": email_id})
        return None

def should_learn(learn_type):
    return (
        learn_type is not None
        and config.SPAM_LEARNING != "off"
        and (
            (learn_type == "spam" and config.SPAM_LEARNING in ("spam", "both"))
            or (learn_type == "ham" and config.SPAM_LEARNING in ("ham", "both"))
        )
    )

def learn_sentence(learn_type, dry_run):
    if dry_run:
        if learn_type == "ham":
            return "Would have submitted to rspamd as ham."
        if learn_type == "spam":
            return "Would have submitted to rspamd as spam."
    else:
        if learn_type == "ham":
            return "Submitted to rspamd as ham."
        if learn_type == "spam":
            return "Submitted to rspamd as spam."
    return ""

def learn_spam(raw_message, email_id=None):
    return _learn(raw_message, "spam", email_id)

def learn_ham(raw_message, email_id=None):
    return _learn(raw_message, "ham", email_id)

def _learn(raw_message, learn_type, email_id=None):
    url = f"http://{config.RSPAMD_HOST}:{config.RSPAMD_CONTROLLER_PORT}/learn{learn_type}"
    logger.debug("Submitting message to rspamd for %s learning at %s", learn_type, url, extra={"email_id": email_id})

    try:
        response = requests.post(
            url,
            data=raw_message,
            headers={
                "Content-Type": "text/plain",
                "Password": config.RSPAMD_PASSWORD
            },
            timeout=10
        )

        if response.status_code != 200:
            logger.warning(
                "rspamd learning returned status %s: %s",
                response.status_code,
                response.text,
                extra={"email_id": email_id}
            )
            return False

        logger.info(
            "rspamd %s learning response: %s",
            learn_type,
            response.text.strip(),
            extra={"email_id": email_id}
        )
        return True

    except requests.exceptions.Timeout:
        logger.error("rspamd learning request timed out", extra={"email_id": email_id})
        return False

    except requests.exceptions.ConnectionError:
        logger.error("Could not connect to rspamd at %s", url, extra={"email_id": email_id})
        return False

    except Exception as e:
        logger.error("Unexpected error during rspamd learning: %s", e, extra={"email_id": email_id})
        return False