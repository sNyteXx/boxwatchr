import requests
from boxwatchr import config
from boxwatchr.logger import get_logger

logger = get_logger("boxwatchr.spam")

RSPAMD_URL = f"http://{config.RSPAMD_HOST}:{config.RSPAMD_PORT}/checkv2"


def check(raw_message, email_id=None):
    logger.debug("Submitting message to rspamd at %s", RSPAMD_URL, extra={"email_id": email_id})

    try:
        response = requests.post(
            RSPAMD_URL,
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
            logger.info(
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
        logger.error("Could not connect to rspamd at %s", RSPAMD_URL, extra={"email_id": email_id})
        return None

    except Exception as e:
        logger.error("Unexpected error during spam check: %s", e, extra={"email_id": email_id})
        return None

def learn_spam(raw_message, email_id=None):
    _learn(raw_message, "spam", email_id)


def learn_ham(raw_message, email_id=None):
    _learn(raw_message, "ham", email_id)


def _learn(raw_message, learn_type, email_id=None):
    url = f"http://{config.RSPAMD_HOST}:{config.RSPAMD_PORT}/learn{learn_type}"
    logger.debug("Submitting message to rspamd for %s learning at %s", learn_type, url, extra={"email_id": email_id})

    try:
        response = requests.post(
            url,
            data=raw_message,
            headers={"Content-Type": "text/plain"},
            timeout=10
        )

        if response.status_code != 200:
            logger.error(
                "rspamd learning returned status %s: %s",
                response.status_code,
                response.text,
                extra={"email_id": email_id}
            )
            return

        logger.info(
            "rspamd %s learning response: %s",
            learn_type,
            response.text.strip(),
            extra={"email_id": email_id}
        )

    except requests.exceptions.Timeout:
        logger.error("rspamd learning request timed out", extra={"email_id": email_id})

    except requests.exceptions.ConnectionError:
        logger.error("Could not connect to rspamd at %s", url, extra={"email_id": email_id})

    except Exception as e:
        logger.error("Unexpected error during rspamd learning: %s", e, extra={"email_id": email_id})