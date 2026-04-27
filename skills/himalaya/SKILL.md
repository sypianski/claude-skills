---
name: himalaya
description: Read, search, and draft email via the himalaya CLI across all configured IMAP accounts. NEVER sends — only saves drafts to the user's Drafts folder for them to send manually. Use when the user asks to check email, search for messages, write a reply, or draft a new message. Activates on /himalaya or intents like "check my mail", "draft a reply to X", "any new email from Y".
metadata:
  short-description: Read mail and save drafts via himalaya (no sending)
---

# Himalaya Email

Read, search, and draft email via the [`himalaya`](https://pimalaya.org/himalaya/) CLI. Multi-account: **always check all configured accounts unless the user names one**. **Never send — only save drafts.** User clicks send themselves from their mail client.

## Hard rules

1. **Never run `himalaya message send`, `himalaya template send`, `curl ... smtp`, or any Python `sendmail` / `SMTP.send`.** Drafts only.
2. **Search across all accounts.** Loop over the account list discovered via `himalaya account list`. Don't default to the first one.
3. **Save drafts via `himalaya message save -f <DraftsFolder> -a <account>`.** Each provider uses a different Drafts folder name (table below).
4. **Confirm with the user before saving** — show them the draft body first, then save once they OK it.
5. After saving a draft, tell the user the account + folder so they can find it in their mail client.
6. **Always build the body as `multipart/alternative` with markdown rendered to HTML** (see "Body format" below). Never save a plain-text-only `MIMEText(...)` draft. Users write/think in markdown; recipients see formatted HTML, plain-text fallback is the raw markdown.
7. **Replies must thread.** Any draft that responds to an existing message MUST carry `In-Reply-To` + `References` headers built from the parent's `Message-ID`. A reply without these headers lands as a brand-new conversation in the recipient's client and breaks the thread on the user's side too. See "Writing a draft reply (threading)" — no exceptions, no "small reply doesn't need it". If you cannot fetch the parent's `Message-ID`, stop and ask the user instead of saving an orphan draft.

## Discover the user's accounts

Don't hardcode account names. Pull them from himalaya at the start of a session:

```bash
himalaya account list
```

Each row is one account alias the user has configured in `~/.config/himalaya/config.toml`. Use those aliases as `-a <account>` arguments.

## Drafts folder names by provider

IMAP folder names for Drafts are **not** standardised — they depend on the provider and the account's UI language. Build a per-account map at the start of a session:

```bash
for acct in $(himalaya account list --output json | jq -r '.[].name'); do
  echo "=== $acct ==="
  himalaya folder list -a "$acct" | grep -i -E 'draft|sent'
done
```

Common cases you'll encounter:

| Provider | Drafts folder | Sent folder | Notes |
|---|---|---|---|
| Gmail (English UI) | `[Gmail]/Drafts` | `[Gmail]/Sent Mail` | |
| Gmail (Polish UI) | `[Gmail]/Wersje robocze` | `[Gmail]/Wysłane` | folder names follow account UI language |
| Gmail (German UI) | `[Gmail]/Entwürfe` | `[Gmail]/Gesendet` | same — locale-dependent |
| iCloud | `Drafts` | `Sent Messages` | quote `"Sent Messages"` (space) |
| Outlook / Microsoft 365 | `Drafts` | `Sent` | |
| Generic IMAP / Dovecot | `Drafts` | `Sent` | |

If the folder list ever drifts, regenerate with `himalaya folder list -a <account> | grep -i -E 'draft|sent'`.

## Reading

```bash
# List newest 20 in INBOX of one account
himalaya envelope list -a <account>

# Filtered (himalaya query language)
himalaya envelope list -a <account> "after 2026-04-20 and subject invoice"
himalaya envelope list -a <account> -f "[Gmail]/All Mail" "from foo@bar.com"

# Read message N from INBOX (id from envelope list)
himalaya message read -a <account> <id>

# Need raw headers (Message-ID, References) for threading?
himalaya message read -a <account> -H Message-ID -H References -H In-Reply-To <id>
```

**Cross-account search pattern** (default for "check my mail" / "any mail from X"):

```bash
for acct in $(himalaya account list --output json | jq -r '.[].name'); do
  echo "=== $acct ==="
  himalaya envelope list -a "$acct" "$QUERY" 2>/dev/null | head -20
done
```

If one account fails (auth/network), keep going with the rest. Report which ones failed at the end.

## Body format (MANDATORY)

Every draft body is `multipart/alternative`:
- **Part 1: `text/plain`** — raw markdown source (readable as-is in plain-text clients).
- **Part 2: `text/html`** — markdown rendered to HTML.

Order matters: HTML must be the **last** part — clients pick the last alternative they understand.

Render with Python `markdown` (`pip install markdown` if missing). Use extensions `extra`, `sane_lists`, `tables`, `fenced_code` so `**bold**`, lists, tables, and code fences all work. For GFM specifics (task lists, autolinks, strikethrough), prefer `pandoc -f gfm -t html`.

The body builder below is the canonical helper — copy it verbatim, fill in headers/body/account/folder, then save.

## Writing a draft (new message)

1. Build an RFC 5322 .eml as `multipart/alternative` with rendered HTML:

   ```python
   import markdown
   from email.mime.multipart import MIMEMultipart
   from email.mime.text import MIMEText
   from email.utils import formataddr, formatdate, make_msgid

   md_body = """\
   Hi Alice,

   Quick update — **the migration ran clean**. Notes:

   - row count matches
   - no FK violations
   - rollback script tested

   Talk soon,
   Your Name
   """

   html_inner = markdown.markdown(
       md_body,
       extensions=["extra", "sane_lists", "tables", "fenced_code"],
   )
   html_doc = f"""<!doctype html><html><head><meta charset="utf-8"></head><body>{html_inner}</body></html>"""

   msg = MIMEMultipart("alternative")
   msg["From"]       = formataddr(("Your Name", "you@example.com"))
   msg["To"]         = "recipient@example.com"
   msg["Subject"]    = "Subject line"
   msg["Date"]       = formatdate(localtime=True)
   msg["Message-ID"] = make_msgid(domain="example.com")
   msg.attach(MIMEText(md_body,  "plain", "utf-8"))   # MUST be first
   msg.attach(MIMEText(html_doc, "html",  "utf-8"))   # MUST be last
   open("/tmp/draft.eml", "wb").write(msg.as_bytes())
   ```

2. Show the markdown body to the user, get OK.

3. Save to Drafts:

   ```bash
   cat /tmp/draft.eml | himalaya message save -a <account> -f "<DraftsFolder>"
   ```

   Quote the folder if it has a space (e.g. `"Sent Messages"`, `"Wersje robocze"`).

4. Confirm to user: account name + folder. Done.

**Forbidden shortcut:** do NOT use `MIMEText(body, "plain")` as the whole message. Even one-line replies go through the multipart/alternative builder — markdown rendering is the user's default, no exceptions.

## Writing a draft reply (threading) — MANDATORY for any response

Replies MUST thread into the original conversation. Mail clients (Gmail web/app, Apple Mail, Outlook, K-9, etc.) determine threading from the `In-Reply-To` and `References` headers per RFC 5322 — not from subject matching alone. A draft missing these headers shows up as a fresh conversation, and once sent, the recipient sees a disconnected message; even worse, the user's own thread loses continuity.

### Step 1 — fetch parent headers

Use himalaya's `-H` flag to expose the headers that would otherwise be stripped from the rendered output:

```bash
himalaya message read -a <account> \
  -H Message-ID -H References -H In-Reply-To -H Subject -H From \
  <parent-envelope-id>
```

Capture three values from the output:

- `parent_message_id` — the parent's `Message-ID:` value, verbatim including angle brackets (e.g. `<CABc123...@mail.gmail.com>`).
- `parent_refs` — the parent's `References:` value (may be empty if parent itself was the start of the thread; that's fine).
- `parent_subject` — the parent's `Subject:` value.

If `Message-ID` is missing or unreadable, **abort and ask the user**. Don't fabricate one and don't save without it.

### Step 2 — set threading headers on the reply

On the same `MIMEMultipart("alternative")` object built per "Body format":

```python
msg["In-Reply-To"] = parent_message_id
msg["References"]  = (parent_refs + " " + parent_message_id).strip()  # append parent at the end
msg["Subject"]     = parent_subject if parent_subject.lower().startswith("re:") else "Re: " + parent_subject
msg["To"]          = parent_from   # default; override if user wants different recipient
```

Notes:
- `References` is a **space-separated chain** of every Message-ID up the thread. Append the parent's Message-ID, never replace. If `parent_refs` is empty, `References` becomes just `parent_message_id`.
- Keep the angle brackets exactly as they appear in the parent header.
- Subject prefix: only add `Re: ` if the parent didn't already start with `Re:` / `re:` / `RE:` — avoid `Re: Re: Re:` chains.
- Localised prefixes (`Odp:`, `Aw:`, `R:`) — leave them alone, just prepend `Re: ` once. Most clients normalise.

### Step 3 — save and verify

Save same way as a new draft: `himalaya message save -a <account> -f "<DraftsFolder>" < /tmp/reply.eml`.

Verify the draft has the headers (one quick check before reporting done):

```bash
himalaya envelope list -a <account> -f "<DraftsFolder>" | head -3
# then read the new draft:
himalaya message read -a <account> -f "<DraftsFolder>" -H In-Reply-To -H References <new-id>
```

If `In-Reply-To` is empty in the saved draft, something stripped it — re-check the .eml before telling the user.

Body still goes through the markdown→HTML multipart/alternative builder. Replies are not exempt from formatting either.

## Output to user

- After cross-account search: short summary per account (count + senders/subjects of recent matches), not a dump.
- After saving a draft: one line — `Draft saved: <account> / <folder>. Open your mail client to review and send.`
- Never claim a message was sent. The skill cannot send.

## Troubleshooting

| Symptom | Fix |
|---|---|
| Account auth fails | Check the `auth.cmd` in `~/.config/himalaya/config.toml`. App passwords for Gmail/iCloud usually live in a secret store (`pass`, `keychain`, or a `.secrets` file with mode 600); OAuth-only providers (Outlook, university Google Workspace) often need a local OAuth bridge like [davmail](https://davmail.sourceforge.net/) or `oauth2-proxy` running on `127.0.0.1:<port>`. |
| Folder name not found | `himalaya folder list -a <account>` — IMAP folder names vary by locale (e.g. Polish Gmail uses `Wersje robocze` for Drafts, German uses `Entwürfe`). |
| Draft appears as "regular" mail in client | `himalaya message save` should set the `\Draft` flag automatically; if not, fall back to Python `imaplib`: build the .eml as above, then `M.append('"<DraftsFolder>"', '\\Draft', imaplib.Time2Internaldate(time.time()), raw)` over an `IMAP4_SSL` connection. CRLF line endings required (`raw = eml_bytes.replace(b'\r\n', b'\n').replace(b'\n', b'\r\n')`). |
| User asks to actually send | Refuse and remind them this skill is drafts-only. Point them at their mail client. If the user explicitly wants to send from the terminal, the manual `himalaya message send -a <account>` command is theirs to run — never the skill. |

## Examples

- `/himalaya any mail from john today?` → loop accounts, `envelope list ... "after <today> and from john"`, summarise.
- `/himalaya draft a reply to envelope 1873 in <account> saying I'll be there at 6` → fetch parent, build reply with In-Reply-To + References, show body, save to `<account> / <DraftsFolder>`.
- `/himalaya new mail to alice@x.com subject "lunch?" body "free thursday?"` → build .eml, ask which account to send from (default first one), save to that account's Drafts.
