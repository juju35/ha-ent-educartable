# Changelog

## 0.3.0 - 2026-11-24

### Features
- Sign a liaison-book message from the card or the panel (a confirmation at the top with the signer's name, prefilled), or mark it as read; `educartable.sign` and `educartable.mark_read` actions. Administrators only.
- Tick a homework that asks to be done, child by child, from the card, the panel or the new to-do lists.
- Rows unfold to the message's or homework's text, its author and its attachments: images shown, PDFs and other files opened through Home Assistant (signed link, administrators only).
- A **Homework** calendar (every child's homework on its due date) and one **Homework** to-do list per child.
- `educartable_new_homework`, `educartable_new_message` and `educartable_new_news` events, and optional notifications to the notify actions of your choice (options and panel Settings).
- **Reconfigure**: change the credentials, or switch each one between a stored value and a `secrets.yaml` entry.

### Fixes
- A liaison-book message is to sign when it asks for a signature that nobody gave yet, as the portal's own app decides it (it was read from its recipients' boxes).
- Diagnostics no longer contain any title, name or class: only counts.

## 0.2.0 - 2026-11-24

### Features
- `custom:educartable-card`, shipped with the integration and added to the dashboard resources: the illustrated school-corner header (the envelope of the liaison book to sign, the pen of the homework left), counts of homework, messages to sign and news, then the liaison book to sign, the homework of every child and the news (events and parent meetings told apart).
- `custom:educartable-mini-card`: the counts, with a button to open the full card in place.
- Educartable sidebar panel: Home (child filter, school week, tiles, To do and news), Homework (one box per due day with its progress), Liaison book, News and Settings tabs; the top bar folds on scroll.
- A badge on the panel's sidebar entry: messages to sign and homework to do, summed over every account.
- New options, also set from the panel: show the panel, the tabs it shows and who its top bar is hidden for.
- A **Last update** sensor carrying the children and the panel options; each homework sensor now says whose homework it is.
- The integration is translated into the 22 languages of the other ha-* projects (only English and French before).

## 0.1.0 - 2026-11-23

### Features
- First read-only release. Signs in to the Educartable family portal (OpenID Connect, with optional two-factor code; credentials can live in `secrets.yaml`) and exposes, for every account:
  - one device per child with a **Homework to do** sensor (count + the homework in its attributes),
  - a **Liaison book to sign** sensor (count of messages still to sign, across all children),
  - a **News** sensor (recent news, events and parent meetings).
- A `educartable.refresh` action to fetch the latest data on demand.
