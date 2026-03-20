import os
import sys
import signal
import time
import socket
import threading
import requests
from imapclient import IMAPClient
from boxwatchr import config
from boxwatchr.database import flush as flush_db, initialize as db_initialize, start_flusher as db_start_flusher, verify as db_verify, DB_PATH as _db_path
from boxwatchr import imap as _imap
from boxwatchr.rules import load_rules as _load_rules
from boxwatchr.logger import get_logger

logger = get_logger("boxwatchr.health")

_MONITOR_INTERVAL = 60
_RETRY_INTERVAL = 5
_MAX_FAILURES = 10
_STARTUP_CHECK_INTERVAL = 5
_STARTUP_PER_SERVICE_TIMEOUT = 30
_DIVIDER = "=" * 35


def _tcp_check(host, port):
    try:
        s = socket.create_connection((host, port), timeout=2)
        s.close()
        return True, ""
    except OSError as e:
        return False, str(e)


def _check_rspamd():
    try:
        url = "http://%s:%s/ping" % (config.RSPAMD_HOST, config.RSPAMD_PORT)
        response = requests.get(url, timeout=2)
        if response.text.strip() == "pong":
            return True, ""
        return False, "unexpected response: %s" % response.text.strip()
    except requests.exceptions.RequestException as e:
        return False, str(e)


def _check_redis():
    return _tcp_check("127.0.0.1", 6379)


def _check_unbound():
    return _tcp_check("127.0.0.1", 5335)


def _check_web():
    return _tcp_check("127.0.0.1", 80)


def _check_imap():
    try:
        client = IMAPClient(config.IMAP_HOST, port=config.IMAP_PORT, ssl=True)
    except Exception as e:
        return False, str(e), False

    try:
        client.login(config.IMAP_USERNAME, config.IMAP_PASSWORD)
    except Exception as e:
        try:
            client.logout()
        except Exception:
            pass
        return False, "authentication failed: %s" % e, True

    try:
        client.select_folder(config.IMAP_FOLDER)
        client.logout()
        return True, "", False
    except Exception:
        reason = "folder %r does not exist on the server" % config.IMAP_FOLDER
        try:
            folders = client.list_folders()
            names = sorted(f[2] for f in folders)
            reason += ". We found these folders:\n" + "\n".join("- %s" % n for n in names)
        except Exception:
            pass
        try:
            client.logout()
        except Exception:
            pass
        return False, reason, True


def initialize_database():
    print(_DIVIDER, flush=True)
    print("Initializing database...", flush=True)
    print(_DIVIDER, flush=True)

    logger.info("Initializing database at %s", _db_path)

    try:
        db_initialize()
        db_start_flusher()
        db_verify()
    except Exception as e:
        logger.error("Fatal: database initialization failed: %s\n\nShutting down.", e)
        fatal_shutdown()

    logger.info("Database ready.")
    print(flush=True)


def fatal_shutdown():
    flush_db()
    os.kill(1, signal.SIGTERM)
    sys.exit(2)


def load_rules_startup(path):
    print(_DIVIDER, flush=True)
    print("Loading rules...", flush=True)
    print(_DIVIDER, flush=True)

    try:
        loaded_rules = _load_rules(path)
    except Exception as e:
        logger.error("Fatal: could not load rules from %s: %s\n\nShutting down.", path, e)
        fatal_shutdown()

    logger.info("Loaded %s valid rule(s)", len(loaded_rules))
    print(flush=True)
    return loaded_rules


_STARTUP_SERVICES = [
    ("Unbound", _check_unbound),
    ("Redis", _check_redis),
    ("rspamd", _check_rspamd),
]


def start_services_sequentially():
    for name, check_fn in _STARTUP_SERVICES:
        print(_DIVIDER, flush=True)
        print("Starting: %s service..." % name, flush=True)
        print(_DIVIDER, flush=True)

        deadline = time.monotonic() + _STARTUP_PER_SERVICE_TIMEOUT
        ready = False
        last_reason = ""

        while time.monotonic() < deadline:
            result = check_fn()
            ok, reason = result[0], result[1]
            fatal = result[2] if len(result) > 2 else False
            if ok:
                ready = True
                break
            if fatal:
                logger.error(
                    "Fatal: %s service failed to start: %s\n\nShutting down.",
                    name, reason
                )
                fatal_shutdown()
            last_reason = reason
            logger.debug("Waiting for %s to be ready...", name)
            time.sleep(_STARTUP_CHECK_INTERVAL)

        if not ready:
            if last_reason:
                logger.error(
                    "Fatal: %s service did not start within %ds: %s\n\nShutting down.",
                    name, _STARTUP_PER_SERVICE_TIMEOUT, last_reason
                )
            else:
                logger.error(
                    "Fatal: %s service did not start within %ds.\n\nShutting down.",
                    name, _STARTUP_PER_SERVICE_TIMEOUT
                )
            fatal_shutdown()

        logger.info("%s service is up and ready.", name)
        print(flush=True)


def start_imap(loaded_rules):
    print(_DIVIDER, flush=True)
    print("Starting: IMAP service...", flush=True)
    print(_DIVIDER, flush=True)

    deadline = time.monotonic() + _STARTUP_PER_SERVICE_TIMEOUT
    client = None
    last_reason = ""

    while time.monotonic() < deadline:
        try:
            client = IMAPClient(config.IMAP_HOST, port=config.IMAP_PORT, ssl=True)
        except Exception as e:
            last_reason = str(e)
            logger.debug("Waiting for IMAP to be ready...")
            time.sleep(_STARTUP_CHECK_INTERVAL)
            continue

        try:
            client.login(config.IMAP_USERNAME, config.IMAP_PASSWORD)
        except Exception as e:
            try:
                client.logout()
            except Exception:
                pass
            logger.error("Fatal: IMAP authentication failed: %s\n\nShutting down.", e)
            fatal_shutdown()

        logger.info("Connected to %s:%s as %s", config.IMAP_HOST, config.IMAP_PORT, config.IMAP_USERNAME)
        break
    else:
        logger.error(
            "Fatal: IMAP service did not start within %ds: %s\n\nShutting down.",
            _STARTUP_PER_SERVICE_TIMEOUT, last_reason
        )
        fatal_shutdown()

    try:
        if not config.IMAP_TRASH_FOLDER or not config.IMAP_SPAM_FOLDER:
            detected_trash, detected_junk = _imap.detect_special_folders(client)

            if not config.IMAP_TRASH_FOLDER:
                if detected_trash:
                    config.IMAP_TRASH_FOLDER = detected_trash
                    logger.info("Trash folder auto-detected: %s", config.IMAP_TRASH_FOLDER)
                else:
                    logger.error(
                        "Fatal: Trash folder not configured and could not be detected. "
                        "Set IMAP_TRASH_FOLDER in .env\n\nShutting down."
                    )
                    fatal_shutdown()

            if not config.IMAP_SPAM_FOLDER:
                if detected_junk:
                    config.IMAP_SPAM_FOLDER = detected_junk
                    logger.info("Spam folder auto-detected: %s", config.IMAP_SPAM_FOLDER)
                else:
                    logger.error(
                        "Fatal: Spam folder not configured and could not be detected. "
                        "Set IMAP_SPAM_FOLDER in .env\n\nShutting down."
                    )
                    fatal_shutdown()

        try:
            folder_names = _imap.list_folder_names(client)
        except Exception as e:
            logger.error("Fatal: Could not list IMAP folders: %s\n\nShutting down.", e)
            fatal_shutdown()

        folder_set = set(folder_names)
        folder_list = "\n".join("- %s" % f for f in folder_names)

        if config.IMAP_FOLDER not in folder_set:
            logger.error(
                "Fatal: Watched folder %r does not exist on the server. We found these folders:\n%s\n\nShutting down.",
                config.IMAP_FOLDER, folder_list
            )
            fatal_shutdown()

        destinations = {
            action["destination"]
            for rule in loaded_rules
            for action in rule["actions"]
            if action["type"] == "move"
        }
        missing = [d for d in sorted(destinations) if d not in folder_set]
        if missing:
            logger.error(
                "Fatal: Rule destination folder(s) not found on the server: %s\n\nWe found these folders:\n%s\n\nShutting down.",
                ", ".join(missing), folder_list
            )
            fatal_shutdown()

        logger.info("All IMAP folders verified on server")

    finally:
        try:
            client.logout()
        except Exception:
            pass

    logger.info("IMAP service is up and ready.")
    print(flush=True)


def service_check():
    checks = {
        "rspamd": _check_rspamd,
        "redis": _check_redis,
        "unbound": _check_unbound,
        "web": _check_web,
        "imap": _check_imap,
    }
    failed = [name for name, fn in checks.items() if not fn()[0]]
    if failed:
        logger.warning("Service check failed: %s", ", ".join(failed))
    else:
        logger.debug("All services healthy")
    return failed


def wait_for_services():
    logger.info("Waiting for all services to recover...")
    while True:
        failed = service_check()
        if not failed:
            logger.info("All services recovered")
            return
        time.sleep(_RETRY_INTERVAL)


def _monitor_loop():
    consecutive_failures = 0
    while True:
        time.sleep(_MONITOR_INTERVAL)
        failed = service_check()
        if not failed:
            if consecutive_failures > 0:
                logger.info("All services recovered after %s failure(s)", consecutive_failures)
            consecutive_failures = 0
        else:
            consecutive_failures += 1
            logger.error(
                "Service check failed (%s/%s consecutive failures)",
                consecutive_failures, _MAX_FAILURES
            )
            if consecutive_failures >= _MAX_FAILURES:
                logger.error(
                    "Services have been unavailable for too long. Still failing: %s. Shutting down.",
                    ", ".join(failed)
                )
                fatal_shutdown()


def start_monitor():
    t = threading.Thread(target=_monitor_loop, daemon=True, name="health-monitor")
    t.start()
    logger.debug("Health monitor started, checking every %s seconds", _MONITOR_INTERVAL)
