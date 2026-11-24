# ha-ent-educartable

[![Marketplace](https://img.shields.io/badge/Marketplace-Custom-41BDF5.svg)](https://www.home-assistant.io/integrations/marketplace/)
[![HACS Validation](https://github.com/juju35/ha-ent-educartable/actions/workflows/hacs.yml/badge.svg)](https://github.com/juju35/ha-ent-educartable/actions/workflows/hacs.yml)
[![Validate](https://github.com/juju35/ha-ent-educartable/actions/workflows/validate.yml/badge.svg)](https://github.com/juju35/ha-ent-educartable/actions/workflows/validate.yml)
[![Lint](https://github.com/juju35/ha-ent-educartable/actions/workflows/lint.yml/badge.svg)](https://github.com/juju35/ha-ent-educartable/actions/workflows/lint.yml)
[![Release](https://img.shields.io/github/v/release/juju35/ha-ent-educartable)](https://github.com/juju35/ha-ent-educartable/releases/latest)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://github.com/juju35/ha-ent-educartable/blob/main/LICENSE)
[![Buy Me a Coffee](https://img.shields.io/badge/Buy%20Me%20a%20Coffee-FFDD00?logo=buymeacoffee&logoColor=black)](https://buymeacoffee.com/julienstep9)

<p align="center"><img src="https://raw.githubusercontent.com/juju35/ha-ent-educartable/main/custom_components/educartable/brand/icon.png" alt="Educartable" width="120"></p>

Home Assistant integration for **Educartable**, the family portal of EDUMOOV used by many French primary schools: homework of every child, liaison book to sign, surveys, parent meetings to book, the private conversation with the teacher, the class life (cahier de vie), the school reports (livret) and school news, with a Lovelace card and a sidebar panel included.

[![Open your Home Assistant instance and open a repository inside the Marketplace.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/marketplace_repository/?owner=juju35&repository=ha-ent-educartable&category=integration)

<img src="https://raw.githubusercontent.com/juju35/ha-ent-educartable/main/screenshots/card.png" alt="educartable-card" width="380">

> [!IMPORTANT]
> Unofficial community project, neither made nor endorsed by EDUMOOV or Educartable. The portal has no public API: the integration calls the routes its own web application uses, and a portal update can break it. If something does not work on your account, please [open an issue](https://github.com/juju35/ha-ent-educartable/issues).

## Features

- One device per child with a **Homework to do** sensor: the count, with the homework (title, subject, due date, text, attachments, done) as attributes
- **Liaison book to sign** sensor (messages still to sign, with the ones to read) and **News** sensor (news, events and parent meetings)
- **Class life** sensor (the cahier de vie: the class's posts with their photos, links and likes), **Unread notifications** sensor (the portal's notifications, cancelled appointments included) and **Next appointment** sensor (every appointment booked ahead as attributes)
- **School reports to sign** sensor: the livret (school reports and attestations) still to sign as consulted, with every document as attributes
- **Last update** sensor with the children and the panel options, read by the card and the panel
- **School events** calendar (the events of the news on their day, and the appointments booked for the children), **Homework** calendar (every child's homework on its due date) and one **Homework** to-do list per child: ticking an item marks it done in the portal
- Actions on the portal (administrators only): sign or mark as read a message, reply to the teacher, write a new message, answer a survey, book or cancel an appointment, sign a school report, like a class-life post, mark notifications as read, delete one of your comments; `educartable.refresh` to read the portal now
- `educartable_new_homework`, `educartable_new_message`, `educartable_new_news`, `educartable_new_activity` and `educartable_new_document` events for automations, and optional **notifications** to the notify actions of your choice
- `custom:educartable-card` card, **shipped with the integration** and loaded automatically: counts, liaison book to sign (with confirmation) or to read, homework to tick and news, each unfolding to its text and attachments
- `custom:educartable-mini-card` compact card: the counts, with a button to open the full card
- **Educartable sidebar panel** with Home, Homework, Liaison book, News, Class life, School reports and Settings tabs: surveys, appointment slots, links, *Translate* and the conversation with the teacher (with attachments) under each message, a *New message* form, the next appointments and the portal's notifications on the home page, and a badge on its sidebar entry counting what there is to deal with
- Username and password stored in the entry or read from `secrets.yaml` at every update; optional two-factor code; **⋮ → Reconfigure** switches each credential between a stored value and a secret
- Diagnostics download with counts only: no name, title or message ever leaves Home Assistant
- English, French, German, Spanish, Serbian (Cyrillic and Latin), Italian, Dutch, Portuguese, Polish, Romanian, Danish, Swedish, Bulgarian, Russian, Ukrainian, Hungarian, Slovak, Czech, Slovenian, Latvian and Greek

## Supported integrations

<p><img src="https://raw.githubusercontent.com/juju35/ha-ent-educartable/main/custom_components/educartable/brand/icon.png" alt="Educartable" height="40"></p>

This integration talks directly to the EDUMOOV family portal, so it needs no other Home Assistant integration; the card and the panel read its own sensors only.

- [Educartable — portail familles](https://www.educartable.com/) (EDUMOOV)

## Prerequisites

- Home Assistant 2026.6 or later
- An Educartable family account (username, often your email, and password, given by the school)

## Installation

### Via the Marketplace (recommended)

Click the button below to add the repository directly:

[![Add to the Marketplace](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/marketplace_repository/?owner=juju35&repository=ha-ent-educartable&category=integration)

Then click **Install** and restart Home Assistant.

Or manually:

1. Open **Settings → Marketplace → Add from link** (top right; this needs a GitHub account connected)
2. Add `https://github.com/juju35/ha-ent-educartable` — Type: **Integration**
3. Open **Educartable** and click **Install**
4. Restart Home Assistant

The card is **part of the integration**: at startup it is added to the dashboard resources (`/educartable_static/educartable-card.js`, module). After an install or an update, restart Home Assistant and refresh the browser (clear the companion app cache if needed). If your dashboards are in YAML mode, the card is loaded on every page without going through the resources.

### Manual

Copy `custom_components/educartable/` to `/config/custom_components/educartable/`, then restart Home Assistant.

## Configuration

### Integration

[![Add integration](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=educartable)

**Settings → Devices & services → Add integration → Educartable**, then enter the username (often your email) and password given by the school. If your account uses two-factor authentication, enter the current one-time code as well.

#### Username and password in secrets.yaml

To keep the credentials out of the config entry, leave the username/password fields empty and give the name of a `secrets.yaml` entry instead:

```yaml
# secrets.yaml
educartable_username: "parent@example.com"
educartable_password: "your-password"
```

The secrets are read again at every update: after a password change, editing the secret is enough.

#### Options

**Settings → Devices & services → Educartable → Configure** (or the panel's Settings tab):

- **Update interval** — Educartable is shared by the whole school, so 10 minutes is the minimum.
- **Homework window** — homework due within this many days is shown.
- **Notify actions** — `notify.mobile_app_…` actions told about new homework, liaison-book messages and news. Empty for none.
- **Show the Educartable panel in the sidebar** — on by default.
- **Tabs shown in the panel** — Homework, Liaison book, News: a hidden tab also leaves the home page.
- **Hide the top bar** — *No*, *For everyone* or *For non-admins*: the tabs stay alone at the top of the panel.

### Card

Add the **Educartable** card from the card picker: every option is set in the visual editor. In YAML:

```yaml
type: custom:educartable-card
```

| Option | Default | Description |
|---|---|---|
| `config_entry_id` | first account | Educartable account to show (useful with several accounts) |
| `title` | `Educartable` | Card title |
| `show_title` | `true` | Show the title in the header |
| `show_refresh` | `true` | Show the refresh button |
| `show_words` | `true` | Show the liaison book messages to sign (section and count) |
| `show_homework` | `true` | Show the homework (section and count) |
| `show_done` | `true` | Show the homework already done (after the rest, struck through) |
| `show_news` | `true` | Show the news, events and parent meetings (section and count) |
| `show_empty` | `false` | Keep the sections with nothing to show (the homework section always stays) |
| `max_items` | `5` | Items per section |
| `illustration` | `true` | Illustrated header: a school corner (schoolbag, exercise books, the envelope of the liaison book to sign or the sheet of the homework) on the card's background, the school icon in the status colour (blue: things to deal with, grey: all done, amber: partly updated, red: unavailable); `false` keeps the classic header |
| `illustration_theme` | `auto` | `auto` (follows the Home Assistant theme: night with a dark theme, day with a light theme), `day` or `night` |
| `language` | Auto | Force language: `en`, `fr`, `de`, `es`, `sr`, `sr-Latn`, `it`, `nl`, `pt`, `pl`, `ro`, `da`, `sv`, `bg`, `ru`, `uk`, `hu`, `sk`, `cs`, `sl`, `lv` or `el` (auto-detects from HA settings) |

With two children or more, each row says whose it is. Click a row with a chevron to unfold it: the message's or homework's text and its attachments (images as thumbnails, other files as buttons that open them); a click elsewhere folds it back. A count opens the panel on its tab (or, without the panel, scrolls the card to its section). The open button opens the Educartable portal in a new tab.

**Sign** opens a confirmation at the top of the card with the signer's name, as the portal asks for it (prefilled with the account's name): a signature cannot be undone. **Mark as read** answers a message that asks to be read. The box of a homework that asks to be done ticks it for that child. These actions and the attachments use the parent's account, so they are reserved to administrators: other users see the state (to sign, to read, done) without the buttons.

### Mini card

A compact card for dashboards: homework to do, liaison book to sign and news. The button at the top right opens the full card in place; a click outside the card folds it back.

```yaml
type: custom:educartable-mini-card
```

It takes the same options as `custom:educartable-card` (both: set in the same visual editor); they apply to the full view.

<img src="https://raw.githubusercontent.com/juju35/ha-ent-educartable/main/screenshots/mini-card.png" alt="educartable-mini-card" width="260">

### Panel

The **Educartable** entry of the sidebar opens a panel under the card's illustrated header (school corner, status in the icon's colour, refresh and open buttons), one tab per part of the portal (the tab is kept in the address):

| Tab | Content |
|---|---|
| Home | A child filter (with two children or more), the school week (homework left per day; a click keeps only that day), tiles for the liaison book, homework, news and school reports (count as badge, coloured state line), then *To do* (messages waiting, homework, school reports to sign), the news, the *Next appointments* and the portal's *Notifications* (each marked as read, or all of them) |
| Homework | The child filter, then one box per due day with its progress (done / total), each homework with its text and its box to tick; done ones can be hidden |
| Liaison book | *New message* (to the teacher of the children chosen; one message per classroom), then the messages still waiting first, with their text, attachments, *Sign* / *Mark as read* buttons, their survey (choose the answers, send them for the children concerned, change them until the deadline), their appointment slots and their conversation with the teacher (opened on demand, with a reply box) |
| News | News, events and parent meetings, with their text, attachments and slots: the slot booked for each child (with *Cancel booking*) and the free ones, day by day, to book |
| Class life | The cahier de vie: the class's posts with their photos and links, a heart to like them (with the count) and their conversation with the teacher when it is open |
| School reports | The livret of each child: school reports and attestations, their PDF, and *Sign* (as consulted, with the signer's name) for those still to sign |
| Settings | The account options; only administrators can change them |

With several accounts, a menu at the right of the tabs switches between them. The child filter and *Hide done* are remembered in the browser, and the tabs can be browsed with the arrow keys. On scroll, the top bar folds into a compact sticky bar with round icon tabs.

### Actions

```yaml
action: educartable.sign
data:
  message_id: "12345"
  name: "Camille Martin"
```

`message_id` comes from the `messages` attribute of the **Liaison book to sign** sensor (or `news` of **News**); `name` is recorded with the signature (3 characters or more). The other actions:

| Action | Data |
|---|---|
| `educartable.mark_read` | `message_id` |
| `educartable.reply` | `message_id`, `text`, optional `attachments`: written in the message's conversation with the teacher; a reply the message asks for is recorded as given |
| `educartable.write_message` | `children` (ids from the `children` attribute of **Last update**), `title`, `text`, optional `attachments`: one message per classroom, its files in a first comment |
| `educartable.answer_survey` | `message_id`, `answers` (each question id with the option ids chosen, from the message's `survey` attribute), optional `children` (all those concerned by default); an answer given before is replaced |
| `educartable.book_appointment` | `slot_id` (from the message's `slots` attribute), `child_id` when several children can still book |
| `educartable.cancel_appointment` | `slot_id` of a booked slot |
| `educartable.sign_document` | `document_id` (from the `documents` attribute of **School reports to sign**), `name` |
| `educartable.like_activity` | `activity_id` (from the `activities` attribute of **Class life**), `liked` (`false` takes the like back) |
| `educartable.mark_notifications_read` | `notification_id` (from the `notifications` attribute of **Unread notifications**); all of them without it |
| `educartable.delete_comment` | `message_id`, `comment_id` of one of your own comments |

```yaml
action: educartable.answer_survey
data:
  message_id: "12345"
  answers:
    "1": ["2"]
```

`attachments` lists files of up to 40 MB each (10 at most; pictures, PDF, office documents, audio, video): paths Home Assistant may read (under `allowlist_external_dirs`, e.g. a camera snapshot), or the files chosen with the paperclip in the panel. They act with the parent's account and are reserved to administrators. `educartable.refresh` reads the portal now. With several accounts, add `config_entry_id`.

### Events

| Event | When | Data |
|---|---|---|
| `educartable_new_homework` | A homework to do appears | `id`, `child_id`, `child`, `title`, `subject`, `due` |
| `educartable_new_message` | A liaison-book message waiting for something appears | `id`, `child`, `title`, `achievement`, `author` |
| `educartable_new_news` | A news item appears | `id`, `title`, `type`, `author` |
| `educartable_new_activity` | A class-life post appears | `id`, `title`, `author`, `child` |
| `educartable_new_document` | A school report or an attestation to sign appears | `id`, `child_id`, `child`, `title`, `kind`, `year` |

Every event also carries `config_entry_id`. Nothing fires at startup or after a reload, and an item fires once only.

```yaml
triggers:
  - trigger: event
    event_type: educartable_new_message
    event_data:
      achievement: sign
actions:
  - action: notify.mobile_app_phone
    data:
      title: "To sign for {{ trigger.event.data.child }}"
      message: "{{ trigger.event.data.title }}"
```

### Diagnostics

**Settings → Devices & services → Educartable → ⋮ → Download diagnostics** gives the options and the number of items of each kind. Credentials, names, titles and texts are never included: the portal holds children's data.

## Screenshots

### Animations

The illustrated header of the card and of the panel plays what is waiting: with a message to sign the envelope bobs and its count blinks; with homework left (everything signed), the pen writes on the sheet. When everything is done, the ticked sheet stays still. Animations stop when the system asks for reduced motion.

Card header, liaison book to sign and homework left:

| Light | Dark |
|---|---|
| <img src="https://raw.githubusercontent.com/juju35/ha-ent-educartable/main/screenshots/card-header-liaison-book.gif" alt="card header, liaison book to sign" width="400"> | <img src="https://raw.githubusercontent.com/juju35/ha-ent-educartable/main/screenshots/card-header-liaison-book-dark.gif" alt="card header, liaison book to sign, dark" width="400"> |
| <img src="https://raw.githubusercontent.com/juju35/ha-ent-educartable/main/screenshots/card-header-homework.gif" alt="card header, homework left" width="400"> | <img src="https://raw.githubusercontent.com/juju35/ha-ent-educartable/main/screenshots/card-header-homework-dark.gif" alt="card header, homework left, dark" width="400"> |

Panel header, liaison book to sign and homework left:

| Light | Dark |
|---|---|
| <img src="https://raw.githubusercontent.com/juju35/ha-ent-educartable/main/screenshots/panel-header-liaison-book.gif" alt="panel header, liaison book to sign" width="480"> | <img src="https://raw.githubusercontent.com/juju35/ha-ent-educartable/main/screenshots/panel-header-liaison-book-dark.gif" alt="panel header, liaison book to sign, dark" width="480"> |
| <img src="https://raw.githubusercontent.com/juju35/ha-ent-educartable/main/screenshots/panel-header-homework.gif" alt="panel header, homework left" width="480"> | <img src="https://raw.githubusercontent.com/juju35/ha-ent-educartable/main/screenshots/panel-header-homework-dark.gif" alt="panel header, homework left, dark" width="480"> |

While the portal is read, the refresh button spins until the update finishes.

| Light | Dark |
|---|---|
| <img src="https://raw.githubusercontent.com/juju35/ha-ent-educartable/main/screenshots/refreshing.gif" alt="refresh animation" width="400"> | <img src="https://raw.githubusercontent.com/juju35/ha-ent-educartable/main/screenshots/refreshing-dark.gif" alt="refresh animation dark" width="400"> |

### Card

| Light | Dark |
|---|---|
| <img src="https://raw.githubusercontent.com/juju35/ha-ent-educartable/main/screenshots/card.png" alt="card" width="400"> | <img src="https://raw.githubusercontent.com/juju35/ha-ent-educartable/main/screenshots/card-dark.png" alt="card dark" width="400"> |

A liaison-book message unfolded to its text and attachments:

| Light | Dark |
|---|---|
| <img src="https://raw.githubusercontent.com/juju35/ha-ent-educartable/main/screenshots/card-unfolded.png" alt="unfolded message" width="400"> | <img src="https://raw.githubusercontent.com/juju35/ha-ent-educartable/main/screenshots/card-unfolded-dark.png" alt="unfolded message dark" width="400"> |

Signing: the confirmation at the top of the card, with the signer's name.

| Light | Dark |
|---|---|
| <img src="https://raw.githubusercontent.com/juju35/ha-ent-educartable/main/screenshots/card-sign.png" alt="sign confirmation" width="400"> | <img src="https://raw.githubusercontent.com/juju35/ha-ent-educartable/main/screenshots/card-sign-dark.png" alt="sign confirmation dark" width="400"> |

The mini card, then expanded by its detail button:

| Light | Dark |
|---|---|
| <img src="https://raw.githubusercontent.com/juju35/ha-ent-educartable/main/screenshots/mini-card.png" alt="mini card" width="260"> | <img src="https://raw.githubusercontent.com/juju35/ha-ent-educartable/main/screenshots/mini-card-dark.png" alt="mini card dark" width="260"> |
| <img src="https://raw.githubusercontent.com/juju35/ha-ent-educartable/main/screenshots/mini-card-zoom.png" alt="mini card expanded" width="400"> | <img src="https://raw.githubusercontent.com/juju35/ha-ent-educartable/main/screenshots/mini-card-zoom-dark.png" alt="mini card expanded dark" width="400"> |

The sidebar entry, with a badge counting what there is to deal with (messages to sign, homework to do and school reports to sign):

| Light | Dark |
|---|---|
| <img src="https://raw.githubusercontent.com/juju35/ha-ent-educartable/main/screenshots/sidebar.png" alt="sidebar badge" width="240"> | <img src="https://raw.githubusercontent.com/juju35/ha-ent-educartable/main/screenshots/sidebar-dark.png" alt="sidebar badge dark" width="240"> |

### Panel

Home (child filter, week, tiles, To do, news, next appointments and notifications), the same with the top bar hidden, Homework (one box per day with its progress), Liaison book, News (with a parent meeting to book), Class life, School reports, a survey with the conversation with the teacher, and a new message:

| Light | Dark |
|---|---|
| <img src="https://raw.githubusercontent.com/juju35/ha-ent-educartable/main/screenshots/panel.png" alt="panel" width="480"> | <img src="https://raw.githubusercontent.com/juju35/ha-ent-educartable/main/screenshots/panel-dark.png" alt="panel dark" width="480"> |
| <img src="https://raw.githubusercontent.com/juju35/ha-ent-educartable/main/screenshots/panel-bare.png" alt="panel, top bar hidden" width="480"> | <img src="https://raw.githubusercontent.com/juju35/ha-ent-educartable/main/screenshots/panel-bare-dark.png" alt="panel, top bar hidden, dark" width="480"> |
| <img src="https://raw.githubusercontent.com/juju35/ha-ent-educartable/main/screenshots/panel-homework.png" alt="panel, homework" width="480"> | <img src="https://raw.githubusercontent.com/juju35/ha-ent-educartable/main/screenshots/panel-homework-dark.png" alt="panel, homework, dark" width="480"> |
| <img src="https://raw.githubusercontent.com/juju35/ha-ent-educartable/main/screenshots/panel-words.png" alt="panel, liaison book" width="480"> | <img src="https://raw.githubusercontent.com/juju35/ha-ent-educartable/main/screenshots/panel-words-dark.png" alt="panel, liaison book, dark" width="480"> |
| <img src="https://raw.githubusercontent.com/juju35/ha-ent-educartable/main/screenshots/panel-news.png" alt="panel, news" width="480"> | <img src="https://raw.githubusercontent.com/juju35/ha-ent-educartable/main/screenshots/panel-news-dark.png" alt="panel, news, dark" width="480"> |
| <img src="https://raw.githubusercontent.com/juju35/ha-ent-educartable/main/screenshots/panel-activities.png" alt="panel, class life" width="480"> | <img src="https://raw.githubusercontent.com/juju35/ha-ent-educartable/main/screenshots/panel-activities-dark.png" alt="panel, class life, dark" width="480"> |
| <img src="https://raw.githubusercontent.com/juju35/ha-ent-educartable/main/screenshots/panel-documents.png" alt="panel, school reports" width="480"> | <img src="https://raw.githubusercontent.com/juju35/ha-ent-educartable/main/screenshots/panel-documents-dark.png" alt="panel, school reports, dark" width="480"> |
| <img src="https://raw.githubusercontent.com/juju35/ha-ent-educartable/main/screenshots/panel-conversation.png" alt="panel, survey and conversation" width="480"> | <img src="https://raw.githubusercontent.com/juju35/ha-ent-educartable/main/screenshots/panel-conversation-dark.png" alt="panel, survey and conversation, dark" width="480"> |
| <img src="https://raw.githubusercontent.com/juju35/ha-ent-educartable/main/screenshots/panel-write.png" alt="panel, new message" width="480"> | <img src="https://raw.githubusercontent.com/juju35/ha-ent-educartable/main/screenshots/panel-write-dark.png" alt="panel, new message, dark" width="480"> |

## How it works

The integration signs in with the family account like the portal's web app (OpenID Connect on `accounts.edumoov.com`, client `educlasse`; the access token is renewed with its refresh token, a refused login starts a reauthentication) and reads, at each update, from `app.educartable.com/api/1.0`: the account and the children (`educore/users/me`, `educore/…/pupils`), each child's homework (`educartable/…/messages?type=lesson`), the liaison book and the news (`info`, `alert`, `event`, `advert`, `meeting` messages, with their surveys and appointment slots), the class life (`activity` messages), the livret (`livret/…/notebooks`, `attestations_validations`), the portal's notifications and the appointments booked ahead. A part a school does not use stays empty; a part the portal fails to give keeps its last content and is listed in the sensors' `stale` attribute, and the card then shows *Partly updated*.

What you do goes through the same routes as the portal's app: achievements (sign, read, comment…), the done box of a homework, comments, new messages, likes, and the RPC API of `api.edumoov.com` for surveys, appointments and translation. Attachments and livret PDFs are fetched only when you open them, through `/api/educartable/file/<entry_id>` (administrators only, 25 MB at most); files you attach are sent to `/api/educartable/upload/<entry_id>` (administrators only, 40 MB each), then uploaded to the portal with the reply. The pupil's skills (*compétences*) are not part of the portal's family app: schools publish them in the livret, shown in the School reports tab.

## Development

The card and the panel are written as ES modules in `src/educartable-card/` and `src/educartable-panel/` (entry `index.js`, translations one file per language in `src/educartable-card/i18n/`). `scripts/build-frontend.mjs` assembles them into `custom_components/educartable/frontend/educartable-card.js` and `educartable-panel.js`, which are not committed: build them before running Home Assistant or the tests. The modules share one scope once assembled, so top-level names stay unique; a new module must be listed in its `index.js`.

```bash
npm install --no-save --no-package-lock acorn@8.19.0 && node scripts/build-frontend.mjs
pip install -r requirements_test.txt && pytest
node --test test/*.test.mjs
pip install playwright==1.64.1 pillow && playwright install chromium
python scripts/screenshots.py   # renders the card, mini card and panel stills and the GIFs of the header animations and of the refresh (needs ffmpeg) into screenshots/
```

### Releasing

1. Bump the version in `custom_components/educartable/manifest.json` and `EDUCARTABLE_CARD_VERSION` in `src/educartable-card/card-picker.js`
2. Add a `## <version>` section at the top of [CHANGELOG.md](https://github.com/juju35/ha-ent-educartable/blob/main/CHANGELOG.md)
3. Merge to `main` with a `feat` or `fix` title: the **Release** workflow creates the tag and the GitHub release with the changelog sections as notes

## Translations

The integration, the card and the panel follow the language of Home Assistant (the card's `language` option can force another one). Currently supported:

| Language | Code |
|---|---|
| English | `en` |
| Français | `fr` |
| Deutsch | `de` |
| Español | `es` |
| Српски | `sr` |
| Srpski (latinica) | `sr-Latn` |
| Italiano | `it` |
| Nederlands | `nl` |
| Português (Portugal) | `pt` |
| Polski | `pl` |
| Română | `ro` |
| Dansk | `da` |
| Svenska | `sv` |
| Български | `bg` |
| Русский | `ru` |
| Українська | `uk` |
| Magyar | `hu` |
| Slovenčina | `sk` |
| Čeština | `cs` |
| Slovenščina | `sl` |
| Latviešu | `lv` |
| Ελληνικά | `el` |

Contributions for additional languages are welcome!

## License

[MIT](https://github.com/juju35/ha-ent-educartable/blob/main/LICENSE)

## Support

If you find this project useful, you can support its development:

<a href="https://buymeacoffee.com/julienstep9"><img src="https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png" alt="Buy Me a Coffee" height="50"></a>
