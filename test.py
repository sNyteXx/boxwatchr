import email
from email import policy
from boxwatchr import config
from boxwatchr.database import initialize
from boxwatchr.imap import connect, select_folder
from boxwatchr.rules import load_rules, evaluate
from boxwatchr.spam import check, learn_spam, learn_ham

print(f"RSPAMD_HOST: {config.RSPAMD_HOST}")
print(f"RSPAMD_PORT: {config.RSPAMD_PORT}")
print(f"RSPAMD_CONTROLLER_PORT: {config.RSPAMD_CONTROLLER_PORT}")

initialize()
load_rules("rules.yaml")

client = connect()
select_folder(client)

uids = client.search(["ALL"])
print(f"Found {len(uids)} messages in inbox\n")

for uid in uids:
    response = client.fetch([uid], ["RFC822"])
    raw = response[uid][b"RFC822"]
    msg = email.message_from_bytes(raw, policy=policy.default)

    sender = msg.get("From", "")
    subject = msg.get("Subject", "")
    to = msg.get("To", "")
    recipients = [addr.strip() for addr in to.split(",")] if to else []

    spam_result = check(raw)

    email_data = {
        "sender": sender,
        "recipients": recipients,
        "subject": subject,
        "raw_headers": str(msg.items())
    }

    rule = evaluate(email_data)

    print(f"UID {uid} | From: {sender} | Subject: {subject}")

    if spam_result:
        print(f"Spam score: {spam_result['score']:.2f} | Is spam: {spam_result['is_spam']}")

    if rule:
        print(f"Rule matched: {rule['name']} | Learn: {rule['learn']}")
        if rule["learn"] == "spam":
            learn_spam(raw)
            print("Submitted to rspamd as spam")
        else:
            learn_ham(raw)
            print("Submitted to rspamd as ham")
    elif spam_result and spam_result["is_spam"]:
        print("No rule matched but spam score exceeds threshold")
        if config.SPAM_LEARNING in ("both", "spam"):
            learn_spam(raw)
            print("Submitted to rspamd as spam")
    else:
        print("No rule matched and score is below threshold")
        if config.SPAM_LEARNING in ("both", "ham"):
            learn_ham(raw)
            print("Submitted to rspamd as ham")

    print("-" * 60)

client.logout()
