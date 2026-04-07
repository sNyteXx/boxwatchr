import json
import sqlite3
from flask import render_template, request
from boxwatchr import config
from boxwatchr.database import db_connection, get_rule
from boxwatchr.web.app import app, _require_auth, _score_class, _EMAILS_PAGE_SIZE, logger


def _resolve_rule_name(rule_matched_json):
    """Resolve current rule name via rule_id, falling back to the stored name."""
    if not rule_matched_json:
        return None, None
    try:
        data = json.loads(rule_matched_json)
    except (json.JSONDecodeError, TypeError):
        return None, None
    rule_id = data.get("id")
    stored_name = data.get("name")
    if rule_id:
        rule_row = get_rule(rule_id)
        if rule_row:
            return rule_row["name"], rule_id
    return stored_name, rule_id


@app.route("/emails")
@_require_auth
def emails():
    try:
        page = max(1, int(request.args.get("page", 1)))
    except ValueError:
        page = 1

    folder = request.args.get("folder", "").strip()

    offset = (page - 1) * _EMAILS_PAGE_SIZE
    try:
        with db_connection() as conn:
            if folder:
                total = conn.execute(
                    "SELECT COUNT(*) FROM emails WHERE folder = ?", (folder,)
                ).fetchone()[0]
                rows = conn.execute(
                    """SELECT id, sender, subject, date_received, spam_score,
                              processed_notes, processed, rule_matched
                       FROM emails
                       WHERE folder = ?
                       ORDER BY date_received DESC
                       LIMIT ? OFFSET ?""",
                    (folder, _EMAILS_PAGE_SIZE, offset),
                ).fetchall()
            else:
                total = conn.execute("SELECT COUNT(*) FROM emails").fetchone()[0]
                rows = conn.execute(
                    """SELECT id, sender, subject, date_received, spam_score,
                              processed_notes, processed, rule_matched
                       FROM emails
                       ORDER BY date_received DESC
                       LIMIT ? OFFSET ?""",
                    (_EMAILS_PAGE_SIZE, offset),
                ).fetchall()
    except sqlite3.Error as e:
        logger.error("Failed to query emails (page=%s, folder=%s): %s", page, folder, e)
        raise

    total_pages = max(1, (total + _EMAILS_PAGE_SIZE - 1) // _EMAILS_PAGE_SIZE)

    email_list = []
    for row in rows:
        rule_name, rule_id = _resolve_rule_name(row["rule_matched"])
        email_list.append({
            "id": row["id"],
            "sender": row["sender"],
            "subject": row["subject"],
            "date_received": row["date_received"],
            "spam_score": row["spam_score"],
            "score_class": _score_class(row["spam_score"]),
            "processed_notes": row["processed_notes"],
            "processed": row["processed"],
            "rule_name": rule_name,
            "rule_id": rule_id,
        })

    return render_template(
        "emails.html",
        emails=email_list,
        page=page,
        total_pages=total_pages,
        total=total,
        folder=folder,
        show_logout=bool(config.WEB_PASSWORD),
    )
