import csv
import io
import json
import sqlite3
from flask import render_template, jsonify, request, Response
from boxwatchr import config
from boxwatchr.database import db_connection
from boxwatchr.web.app import app, _require_auth, logger

def _get_stats():
    try:
        with db_connection() as conn:
            total = conn.execute("SELECT COUNT(*) FROM emails").fetchone()[0]
            pending = conn.execute("SELECT COUNT(*) FROM emails WHERE processed = 0").fetchone()[0]

            spam_caught = conn.execute(
                "SELECT COUNT(*) FROM emails WHERE rspamd_learned = 'spam'"
            ).fetchone()[0]

            ham_learned = conn.execute(
                "SELECT COUNT(*) FROM emails WHERE rspamd_learned = 'ham'"
            ).fetchone()[0]

            rule_rows = conn.execute(
                "SELECT JSON_EXTRACT(rule_matched, '$.name') AS rule_name, COUNT(*) AS cnt"
                " FROM emails WHERE rule_matched IS NOT NULL"
                " GROUP BY rule_name ORDER BY cnt DESC"
            ).fetchall()

            rule_counts = [(row["rule_name"], row["cnt"]) for row in rule_rows if row["rule_name"]]

            score_rows = conn.execute(
                "SELECT spam_score FROM emails WHERE spam_score IS NOT NULL"
            ).fetchall()

            buckets = {"<0": 0, "0-2": 0, "2-5": 0, "5-10": 0, "10-15": 0, "15+": 0}
            for row in score_rows:
                s = row["spam_score"]
                if s < 0:
                    buckets["<0"] += 1
                elif s < 2:
                    buckets["0-2"] += 1
                elif s < 5:
                    buckets["2-5"] += 1
                elif s < 10:
                    buckets["5-10"] += 1
                elif s < 15:
                    buckets["10-15"] += 1
                else:
                    buckets["15+"] += 1

            return {
                "total": total,
                "pending": pending,
                "spam_caught": spam_caught,
                "ham_learned": ham_learned,
                "rule_counts": rule_counts,
                "score_buckets": buckets,
            }
    except sqlite3.Error as e:
        logger.error("Failed to query stats: %s", e)
        raise

@app.route("/dashboard")
@_require_auth
def dashboard():
    stats = _get_stats()
    return render_template(
        "dashboard.html",
        stats=stats,
        show_logout=bool(config.WEB_PASSWORD),
    )


@app.route("/api/stats/timeline")
@_require_auth
def api_stats_timeline():
    try:
        with db_connection() as conn:
            emails_per_day = conn.execute(
                "SELECT DATE(date_received) AS date, COUNT(*) AS count"
                " FROM emails"
                " WHERE date_received >= DATE('now', '-30 days')"
                " GROUP BY DATE(date_received)"
                " ORDER BY date"
            ).fetchall()

            spam_trend = conn.execute(
                "SELECT DATE(date_received) AS date,"
                " AVG(spam_score) AS avg_score"
                " FROM emails"
                " WHERE date_received >= DATE('now', '-30 days')"
                " AND spam_score IS NOT NULL"
                " GROUP BY DATE(date_received)"
                " ORDER BY date"
            ).fetchall()

            rules_per_day = conn.execute(
                "SELECT DATE(date_received) AS date,"
                " JSON_EXTRACT(rule_matched, '$.name') AS rule_name,"
                " COUNT(*) AS count"
                " FROM emails"
                " WHERE date_received >= DATE('now', '-30 days')"
                " AND rule_matched IS NOT NULL"
                " GROUP BY DATE(date_received),"
                " JSON_EXTRACT(rule_matched, '$.name')"
                " ORDER BY date"
            ).fetchall()

        return jsonify({
            "emails_per_day": [
                {"date": row["date"], "count": row["count"]}
                for row in emails_per_day if row["date"]
            ],
            "spam_trend": [
                {"date": row["date"], "avg_score": round(row["avg_score"], 2)}
                for row in spam_trend if row["date"]
            ],
            "rules_per_day": [
                {"date": row["date"], "rule_name": row["rule_name"],
                 "count": row["count"]}
                for row in rules_per_day if row["date"] and row["rule_name"]
            ],
        })
    except sqlite3.Error as e:
        logger.error("Failed to query timeline stats: %s", e)
        return jsonify({"error": "Database error"}), 500


@app.route("/api/stats/top-senders")
@_require_auth
def api_stats_top_senders():
    try:
        with db_connection() as conn:
            top_senders = conn.execute(
                "SELECT sender, COUNT(*) AS count"
                " FROM emails WHERE sender IS NOT NULL AND sender != ''"
                " GROUP BY sender ORDER BY count DESC LIMIT 10"
            ).fetchall()

            top_domains = conn.execute(
                "SELECT LOWER(SUBSTR(sender,"
                " INSTR(sender, '@') + 1)) AS domain,"
                " COUNT(*) AS count"
                " FROM emails"
                " WHERE sender IS NOT NULL AND INSTR(sender, '@') > 0"
                " GROUP BY domain ORDER BY count DESC LIMIT 10"
            ).fetchall()

        return jsonify({
            "top_senders": [
                {"sender": row["sender"], "count": row["count"]}
                for row in top_senders
            ],
            "top_domains": [
                {"domain": row["domain"], "count": row["count"]}
                for row in top_domains
            ],
        })
    except sqlite3.Error as e:
        logger.error("Failed to query top senders: %s", e)
        return jsonify({"error": "Database error"}), 500


@app.route("/api/stats/folders")
@_require_auth
def api_folder_stats():
    from boxwatchr import imap as _imap

    folders = _imap.get_folder_list() if config.SETUP_COMPLETE else []

    folder_counts = {}
    try:
        with db_connection() as conn:
            rows = conn.execute(
                "SELECT folder, COUNT(*) AS cnt FROM emails"
                " WHERE account_id = ? GROUP BY folder",
                (config.ACCOUNT_ID,),
            ).fetchall()
            for row in rows:
                folder_counts[row["folder"]] = row["cnt"]
    except sqlite3.Error as e:
        logger.error("Failed to query folder stats: %s", e)

    result = []
    for folder in folders:
        result.append({
            "name": folder,
            "email_count": folder_counts.get(folder, 0),
            "is_watched": folder == config.IMAP_FOLDER,
        })

    known_folders = set(folders)
    for folder_name, count in folder_counts.items():
        if folder_name not in known_folders:
            result.append({
                "name": folder_name,
                "email_count": count,
                "is_watched": folder_name == config.IMAP_FOLDER,
            })

    return json.dumps({"folders": result}), 200, {"Content-Type": "application/json"}


@app.route("/api/export/emails")
@_require_auth
def api_export_emails():
    fmt = request.args.get("format", "csv").lower()
    try:
        with db_connection() as conn:
            rows = conn.execute(
                "SELECT id, sender, subject, date_received, spam_score,"
                " rule_matched, processed_notes, folder"
                " FROM emails ORDER BY date_received DESC LIMIT 10000"
            ).fetchall()

        records = []
        for row in rows:
            rule_name = ""
            if row["rule_matched"]:
                try:
                    rule_name = json.loads(row["rule_matched"]).get("name", "")
                except (json.JSONDecodeError, TypeError):
                    rule_name = ""
            records.append({
                "id": row["id"],
                "sender": row["sender"] or "",
                "subject": row["subject"] or "",
                "date_received": row["date_received"] or "",
                "spam_score": row["spam_score"] if row["spam_score"] is not None else "",
                "rule_matched": rule_name,
                "processed_notes": row["processed_notes"] or "",
                "folder": row["folder"] or "",
            })

        if fmt == "json":
            data = json.dumps(records, indent=2)
            return Response(
                data,
                mimetype="application/json",
                headers={"Content-Disposition":
                          "attachment; filename=emails_export.json"},
            )

        output = io.StringIO()
        fieldnames = ["id", "sender", "subject", "date_received",
                      "spam_score", "rule_matched", "processed_notes",
                      "folder"]
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)
        return Response(
            output.getvalue(),
            mimetype="text/csv",
            headers={"Content-Disposition":
                      "attachment; filename=emails_export.csv"},
        )
    except sqlite3.Error as e:
        logger.error("Failed to export emails: %s", e)
        return jsonify({"error": "Database error"}), 500


@app.route("/api/export/logs")
@_require_auth
def api_export_logs():
    fmt = request.args.get("format", "csv").lower()
    try:
        with db_connection() as conn:
            rows = conn.execute(
                "SELECT id, level, logger_name, message, logged_at"
                " FROM logs ORDER BY logged_at DESC LIMIT 10000"
            ).fetchall()

        records = [
            {
                "id": row["id"],
                "level": row["level"],
                "logger_name": row["logger_name"],
                "message": row["message"],
                "logged_at": row["logged_at"],
            }
            for row in rows
        ]

        if fmt == "json":
            data = json.dumps(records, indent=2)
            return Response(
                data,
                mimetype="application/json",
                headers={"Content-Disposition":
                          "attachment; filename=logs_export.json"},
            )

        output = io.StringIO()
        fieldnames = ["id", "level", "logger_name", "message", "logged_at"]
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)
        return Response(
            output.getvalue(),
            mimetype="text/csv",
            headers={"Content-Disposition":
                      "attachment; filename=logs_export.csv"},
        )
    except sqlite3.Error as e:
        logger.error("Failed to export logs: %s", e)
        return jsonify({"error": "Database error"}), 500
