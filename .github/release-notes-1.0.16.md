### Added
- Added `notify_discord` action type: rules can now send a Discord embed notification via webhook when they match. The embed shows sender, matched rule name, and spam score (color-coded by severity). Webhook URL is stored per-action in the rule definition and validated against the official Discord webhook domain on save.

### Changed
- Renamed action dropdown options "Flag message" and "Remove flag" to "Mark as flagged" and "Mark as unflagged" for consistency with "Mark as read" / "Mark as unread".
- Added a note to the rule form conditions section explaining which address fields normalize punctuation (Username, Subdomain + domain, Domain (no subdomain)) vs. which match the exact text (Full address, Full domain, TLD).
