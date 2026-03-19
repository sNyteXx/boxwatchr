import os
import re
import yaml
import threading
import tldextract
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from boxwatchr.logger import get_logger

logger = get_logger("boxwatchr.rules")

_rules = []
_rules_lock = threading.Lock()

TERMINAL_ACTIONS = {"move", "delete", "junk"}

def load_rules(path):
    global _rules
    logger.info("Loading rules from %s", path)

    try:
        with open(path, "r") as f:
            data = yaml.safe_load(f)
    except FileNotFoundError:
        logger.error("Rules file not found at %s", path)
        raise
    except yaml.YAMLError as e:
        logger.error("Failed to parse rules file: %s", e)
        raise

    if not data or "rules" not in data or not data["rules"]:
        logger.warning("No rules found in %s", path)
        with _rules_lock:
            _rules = []
        return []

    validated = []
    for rule in data["rules"]:
        result = _validate_rule(rule)
        if result:
            validated.append(result)

    logger.info("Loaded %s valid rule(s)", len(validated))

    with _rules_lock:
        _rules = validated

    return validated

def _validate_rule(rule):
    name = rule.get("name", "").strip()
    if not name:
        logger.warning("A rule is missing a name and will be skipped")
        return None

    if "conditions" not in rule or not rule["conditions"]:
        logger.warning("Rule '%s' has no conditions and will be skipped", name)
        return None

    if "actions" not in rule or not rule["actions"]:
        logger.warning("Rule '%s' has no actions and will be skipped", name)
        return None

    if "learn" not in rule:
        logger.warning("Rule '%s' is missing the required 'learn' field and will be skipped", name)
        return None

    learn = rule.get("learn", "").lower().strip()
    if learn not in ("spam", "ham"):
        logger.warning("Rule '%s' has invalid learn value '%s'. Must be 'spam' or 'ham' and will be skipped", name, learn)
        return None

    match = rule.get("match", "all").lower().strip()
    if match not in ("all", "any"):
        logger.warning("Rule '%s' has invalid match value '%s', defaulting to 'all'", name, match)
        match = "all"

    valid_fields = {
        "sender", "sender_local", "sender_domain", "sender_domain_name",
        "sender_domain_root", "sender_domain_tld",
        "recipient", "recipient_local", "recipient_domain", "recipient_domain_name",
        "recipient_domain_root", "recipient_domain_tld",
        "subject", "raw_headers",
        "attachment_name", "attachment_extension", "attachment_content_type",
    }

    valid_operators = {"equals", "contains", "is_empty"}
    valid_actions = {"move", "delete", "junk", "mark_read", "mark_unread"}
    contradictory_pairs = [{"mark_read", "mark_unread"}]

    validated_conditions = []
    for i, condition in enumerate(rule["conditions"]):
        field = condition.get("field", "").strip()
        operator = condition.get("operator", "").strip()
        value = condition.get("value", "")

        if not field:
            logger.warning("Rule '%s' condition %s is missing a field and will be skipped", name, i + 1)
            return None

        if not operator:
            logger.warning("Rule '%s' condition %s is missing an operator and will be skipped", name, i + 1)
            return None

        if value == "" or value is None:
            logger.warning("Rule '%s' condition %s is missing a value and will be skipped", name, i + 1)
            return None

        if field not in valid_fields:
            logger.warning("Rule '%s' condition %s has unknown field '%s' and will be skipped", name, i + 1, field)
            return None

        if operator not in valid_operators:
            logger.warning("Rule '%s' condition %s has unknown operator '%s' and will be skipped", name, i + 1, operator)
            return None

        if operator == "is_empty" and str(value).lower() not in ("true", "false"):
            logger.warning("Rule '%s' condition %s uses is_empty but value must be true or false and will be skipped", name, i + 1)
            return None

        validated_conditions.append({
            "field": field,
            "operator": operator,
            "value": str(value)
        })

    validated_actions = []
    for i, action in enumerate(rule["actions"]):
        action_type = action.get("type", "").strip()

        if not action_type:
            logger.warning("Rule '%s' action %s is missing a type and will be skipped", name, i + 1)
            continue

        if action_type not in valid_actions:
            logger.warning("Rule '%s' action %s has unknown type '%s' and will be skipped", name, i + 1, action_type)
            continue

        if action_type == "move" and not action.get("destination", "").strip():
            logger.warning("Rule '%s' action %s is a move but has no destination and will be skipped", name, i + 1)
            continue

        validated_actions.append(action)

    if not validated_actions:
        logger.warning("Rule '%s' has no valid actions after validation and will be skipped", name)
        return None

    seen_types = []
    for action in validated_actions:
        action_type = action["type"]
        if action_type in seen_types:
            logger.warning("Rule '%s' has duplicate action type '%s' and will be skipped", name, action_type)
            return None
        seen_types.append(action_type)

    terminal_count = sum(1 for a in validated_actions if a["type"] in TERMINAL_ACTIONS)
    if terminal_count > 1:
        logger.warning(
            "Rule '%s' has more than one terminal action (%s) and will be skipped",
            name, "/".join(sorted(TERMINAL_ACTIONS))
        )
        return None

    action_types = {a["type"] for a in validated_actions}
    for pair in contradictory_pairs:
        if pair.issubset(action_types):
            logger.warning(
                "Rule '%s' has contradictory actions %s and will be skipped",
                name, " and ".join(sorted(pair))
            )
            return None

    logger.debug("Rule '%s' validated successfully", name)

    return {
        "name": name,
        "match": match,
        "learn": learn,
        "conditions": validated_conditions,
        "actions": validated_actions
    }

def _extract_fields(email):
    def strip_display_name(address):
        address = address.strip()
        if "<" in address and ">" in address:
            start = address.index("<") + 1
            end = address.index(">")
            return address[start:end].strip()
        return address

    def split_address(address):
        address = strip_display_name(address).lower()
        if "@" not in address:
            return {
                "full": address,
                "local": address,
                "domain": "",
                "domain_name": "",
                "domain_root": "",
                "tld": ""
            }
        local, domain = address.split("@", 1)
        extracted = tldextract.extract(domain)
        domain_root = extracted.domain
        tld = extracted.suffix
        domain_name = f"{extracted.subdomain}.{extracted.domain}" if extracted.subdomain else extracted.domain

        return {
            "full": address,
            "local": local,
            "domain": domain,
            "domain_name": domain_name,
            "domain_root": domain_root,
            "tld": tld
        }

    sender = email.get("sender", "")
    subject = email.get("subject", "")
    recipients = email.get("recipients", [])
    raw_headers = email.get("raw_headers", "")
    raw_attachments = email.get("attachments", [])

    sender_parts = split_address(sender)
    recipient_parts = [split_address(r) for r in recipients]
    attachment_parts = [
        {
            "name": a.get("name", "").lower(),
            "extension": a.get("extension", "").lower(),
            "content_type": a.get("content_type", "").lower(),
        }
        for a in raw_attachments
    ]

    return {
        "sender": sender_parts["full"],
        "sender_local": sender_parts["local"],
        "sender_domain": sender_parts["domain"],
        "sender_domain_name": sender_parts["domain_name"],
        "sender_domain_root": sender_parts["domain_root"],
        "sender_domain_tld": sender_parts["tld"],
        "recipients": recipient_parts,
        "subject": subject.lower(),
        "raw_headers": raw_headers.lower(),
        "attachments": attachment_parts,
    }

def _match_condition(condition, fields, rule_name):
    field = condition["field"]
    operator = condition["operator"]
    value = condition["value"].lower()

    if field.startswith("recipient"):
        recipient_key = {
            "recipient": "full",
            "recipient_local": "local",
            "recipient_domain": "domain",
            "recipient_domain_name": "domain_name",
            "recipient_domain_root": "domain_root",
            "recipient_domain_tld": "tld"
        }.get(field)

        if not fields["recipients"]:
            return _apply_operator(operator, "", value, field, rule_name)

        return any(
            _apply_operator(operator, r.get(recipient_key, ""), value, field, rule_name)
            for r in fields["recipients"]
        )

    if field.startswith("attachment"):
        attachment_key = {
            "attachment_name": "name",
            "attachment_extension": "extension",
            "attachment_content_type": "content_type",
        }.get(field)

        if not fields["attachments"]:
            return _apply_operator(operator, "", value, field, rule_name)

        return any(
            _apply_operator(operator, a.get(attachment_key, ""), value, field, rule_name)
            for a in fields["attachments"]
        )

    field_value = fields.get(field, "")
    return _apply_operator(operator, field_value, value, field, rule_name)

def _normalize(value):
    return re.sub(r"[^a-z0-9]", "", value.lower())

def _apply_operator(operator, field_value, value, field_name, rule_name):
    if operator == "is_empty":
        is_empty = field_value == ""
        return is_empty if value == "true" else not is_empty

    normalized_fields = {
        "sender_local", "sender_domain_name", "sender_domain_root",
        "recipient_local", "recipient_domain_name", "recipient_domain_root"
    }

    if field_name in normalized_fields:
        normalized_field = _normalize(field_value)
        normalized_value = _normalize(value)

        if operator == "equals":
            result = normalized_field == normalized_value
            if result and normalized_field != field_value.lower():
                logger.debug(
                    "Rule matched because '%s' normalized to '%s' matches '%s'",
                    field_value, normalized_field, value
                )
            return result

        if operator == "contains":
            result = normalized_value in normalized_field
            if result and normalized_field != field_value.lower():
                logger.debug(
                    "Rule matched because '%s' normalized to '%s' contains '%s'",
                    field_value, normalized_field, value
                )
            return result

    if operator == "equals":
        return field_value == value
    if operator == "contains":
        return value in field_value

    return False

def evaluate(email):
    fields = _extract_fields(email)
    logger.debug("Evaluating rules for email from %s", fields.get("sender", "unknown"))

    with _rules_lock:
        rules = list(_rules)

    for rule in rules:
        conditions = rule["conditions"]
        match_type = rule["match"]

        results = [_match_condition(c, fields, rule["name"]) for c in conditions]

        if match_type == "all" and all(results):
            logger.info("Email matched rule '%s'", rule["name"])
            return rule

        if match_type == "any" and any(results):
            logger.info("Email matched rule '%s'", rule["name"])
            return rule

    logger.debug("Email did not match any rules")
    return None

class _RulesFileHandler(FileSystemEventHandler):
    def __init__(self, path):
        self.path = path

    def on_modified(self, event):
        if event.src_path.endswith(self.path):
            logger.info("Rules file changed, reloading")
            try:
                load_rules(self.path)
            except Exception as e:
                logger.error("Failed to reload rules: %s", e)

def watch_rules(path):
    logger.info("Watching rules file for changes: %s", path)
    event_handler = _RulesFileHandler(path)
    observer = Observer()
    observer.schedule(event_handler, path=os.path.dirname(os.path.abspath(path)), recursive=False)
    observer.start()
    return observer
