from boxwatchr import config

def action_sentence(action, dry_run):
    t = action["type"]
    dest = action.get("destination", "")
    if dry_run:
        if t == "move":
            return "Would have moved to %s." % dest
        if t == "delete":
            return "Would have moved to trash."
        if t == "spam":
            return "Would have moved to spam."
        if t == "mark_read":
            return "Would have marked as read."
        if t == "mark_unread":
            return "Would have marked as unread."
        if t == "flag":
            return "Would have flagged."
        if t == "unflag":
            return "Would have unflagged."
    else:
        if t == "move":
            return "Moved to %s." % dest
        if t == "delete":
            return "Moved to trash."
        if t == "spam":
            return "Moved to spam."
        if t == "mark_read":
            return "Marked as read."
        if t == "mark_unread":
            return "Marked as unread."
        if t == "flag":
            return "Flagged."
        if t == "unflag":
            return "Unflagged."
    return ""

def failed_action_sentence(action):
    t = action["type"]
    dest = action.get("destination", "")
    if t == "move":
        return "Failed to move to %s." % dest
    if t == "delete":
        return "Failed to move to trash."
    if t == "spam":
        return "Failed to move to spam."
    if t == "mark_read":
        return "Failed to mark as read."
    if t == "mark_unread":
        return "Failed to mark as unread."
    if t == "flag":
        return "Failed to flag."
    if t == "unflag":
        return "Failed to unflag."
    return "Action failed."

def build_notes_opener(matched_rule, spam_score, dry_run):
    prefix = "[DRY RUN] " if dry_run else ""
    if matched_rule:
        return "%sThe rule '%s' matched." % (prefix, matched_rule["name"])
    if spam_score is not None and spam_score >= config.SPAM_THRESHOLD:
        return "%sNo rule matched. Spam score %.1f exceeded threshold." % (prefix, spam_score)
    return "%sNo rule matched." % prefix
