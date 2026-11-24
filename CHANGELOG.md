# Changelog

## 1.1.0 - 2026-11-24

### Features
- Attach files to a reply or a new message: the paperclip in the panel (up to 10 files of 40 MB: pictures, PDF, office documents, audio, video), or `attachments` in `educartable.reply` and `educartable.write_message` with paths Home Assistant may read (a camera snapshot…). A reply can be made of files only; a new message's files go in its first comment, as the portal does.
- *Translate* under a message in the panel, by the portal's own translation, when Home Assistant is not in French; *Show the original* goes back.

## 1.0.0 - 2026-11-24

First stable version: every part of the portal's family app is covered, and the work-in-progress banner is gone.

### Features
- The class life (cahier de vie): a **Class life** sensor and panel tab with the class's posts, their photos and links, a heart to like them and their conversation with the teacher. `educartable.like_activity` action and `educartable_new_activity` event (also notified).
- **Next appointment** sensor with every appointment booked ahead, and a *Next appointments* box on the panel's home page.
- **School events** calendar: the events of the news on their own day and the appointments booked for the children.
- **Unread notifications** sensor with the portal's notifications (a cancelled appointment told with its author and time), shown on the panel's home page and marked as read one by one or all together. `educartable.mark_notifications_read` action.
- Links attached to messages and homework (videos, sites) open from their row.
- Parent meetings say when the child is expected too; archived messages are read only.
- Delete one of your own comments in a conversation. `educartable.delete_comment` action.

### Fixes
- Class-life posts are no longer counted as homework to do.
- An event is dated on its own day, not on the day it was published.

## 0.4.0 - 2026-11-24

### Features
- Reply to the teacher: each message's private conversation opens under it in the panel, with a reply box; a reply the message asks for is recorded as given. `educartable.reply` action.
- Write a new message to the teacher from the Liaison book (*New message*: children, subject, text; one message per classroom, children whose teacher paused messages left out). `educartable.write_message` action.
- Answer surveys: the questions and options under the message, sent for the children concerned and changed until the deadline. `educartable.answer_survey` action.
- Book parent meetings: the slot booked for each child and the free ones, day by day, with a confirmation and the child to book for; cancel a booking. `educartable.book_appointment` and `educartable.cancel_appointment` actions.
- The livret: a **School reports to sign** sensor, a **School reports** tab in the panel (school reports and attestations of each child, their PDF) and *Sign* as consulted with the signer's name. `educartable.sign_document` action and `educartable_new_document` event (also notified).
- The sidebar badge and the panel's home page count the school reports to sign.
- Accounts that chose their panel tabs before get the new School reports tab.

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
