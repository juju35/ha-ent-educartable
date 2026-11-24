# Repository guide for agents

## Commits
- Write every commit message in **English**, following **Conventional Commits**:
  `type(scope): subject` — types: `feat`, `fix`, `chore`, `docs`, `style`, `refactor`,
  `perf`, `test`, `build`, `ci`, `revert`. Subject in imperative mood, lower case,
  no trailing period, ≤ 72 chars.
- Author identity must be **juju35** (`juju35 <julienstephan29@gmail.com>`), never an assistant identity.
- Messages are checked by **commitlint** (Conventional Commits) via the pre-commit
  `commit-msg` hook; run `pre-commit install` once so the hook is active locally.
- **External contributions**: add the contributor as a commit **co-author** (their GitHub
  noreply address) **only** when they supplied a patch/PR or a translation — never for a
  mere idea or feature issue.
- Keep history clean and linear: small, focused commits, one logical change each.
- `main` is protected by a ruleset: **squash-merge only**, the commit message is the PR
  **title + description**; tags follow a `v*` ruleset.

## Before opening a PR — run the checks locally
CI mirrors these; running them first avoids round-trips:
```sh
npm install --no-save --no-package-lock acorn@8.19.0 && node scripts/build-frontend.mjs
pre-commit run -a
vulture custom_components .vulture_whitelist.py --min-confidence 60
npx --yes jscpd@5.4.2 .
pytest
node --test test/*.test.mjs
```

## Releasing — how it works here
A release follows **every `feat` or `fix` merge** on `main` (the squash title) whose version has no
tag yet; `ci`/`docs`/`test`/`chore`/`refactor` merges publish nothing. Other bumps (e.g. `perf`) wait
for the next feat/fix, or run the Release workflow by hand (`gh workflow run release.yml`). The notes
gather the CHANGELOG sections of every version since the previous tag.
**Never create a tag by hand.**

The `Version consistency` check (validate.yml) requires the **same version in every place**,
or the release fails.

## Bumping the version
This is an **INTEGRATION** repo with a card and a panel. A bump is complete only when **every** file below
carries the new version, updated together in one commit:
1. `CHANGELOG.md` → add a "## X.Y.Z - YYYY-MM-DD" section at the top (`### Features` | `Fixes` | `Performance` | `Maintenance`).
2. `custom_components/educartable/manifest.json` → `"version": "X.Y.Z"`.
3. `src/educartable-card/card-picker.js` → `EDUCARTABLE_CARD_VERSION = 'X.Y.Z'`.
- Bump rule: `fix` → patch, `feat` → minor, breaking change → major.
- **Bump only when what users install changes** (shipped code, translations, assets of the
  release). CI, workflows, tests, screenshots, README, lint config, CLAUDE.md: no bump, no
  CHANGELOG entry, no version in the title (e.g. `ci: …`, `docs: …`, `test: …`, `chore: …`).
- A bumping PR/commit title carries the version in parentheses, e.g. `feat: new sensor (X.Y.Z)`.

## Scope and roadmap
- Educartable is **EDUMOOV**'s family portal for primary school — an unofficial, reverse-engineered
  API (`app.educartable.com`, OpenID Connect on `accounts.edumoov.com`, client `educlasse`). It may
  change without notice.
- Two sides: **Élèves** (homework per child) and **Parents** (liaison book, news), with a card, a mini card and a
  sidebar panel (layout of ha-ent-one: card A, mini card with the counts, panel with Home / Homework / Liaison book /
  News / Settings tabs), a homework calendar and a to-do list per child.
- Routes follow the portal's own web app (`mobile.educartable.com`, its `app.*.js` bundle): a message's `achievement`
  is what it asks (read, sign, check, comment, book, survey) and it is done once `achievements` is not empty;
  `POST …/messages/{id}/achieve` (`subject_model`, `subject_key`, `action`, `body` = signer's name for sign),
  `POST …/messages/{id}/check` (`recipient_id`, `checked`, per pupil recipient), attachments at
  `educore/medias/{id}/file`. Writes are **administrators only** (services, websocket, file view).
- Also implemented (0.4.0): the conversation of a message (`educore/…/comments`, model `HomeworkMessage`, `reply` = its first
  comment), new messages (`POST educartable/…/messages` {children of one classroom, title, body}), surveys and appointments
  through the RPC API (`POST https://api.edumoov.com/rpc/<method>` {params, payload}: `parent.messages.answerSurvey` /
  `deleteAnswerSurvey`, `parent.events.register` / `unregister`), the livret (`livret/…/notebooks` and
  `attestations_validations`, signed with `…/{id}/sign` {name}; PDFs at `core/cloudy_files/{file}/file/{hash}/educartable`
  and `livret/attestations_validations/pdf/{id}?hash=`).
- Also implemented (1.0.0, the first stable version, no work-in-progress banner any more): the cahier de vie (`type=activity` messages, never homework; likes `POST core/…/likes`
  {key, model `HomeworkMessage`} → like id, `DELETE core/…/likes/{id}`), notifications (`educore/…/notifications?app=Educartable`,
  unread family ones; read `PUT …/{id}` {read}, all `PUT …/close_all`), booked appointments
  (`cartable.events.nextRegisteredEvents` {start, stop}), message links, `pupil_present`, `archived`, comment deletion
  (`DELETE educore/…/comments/{id}/trash`). Events are dated by their `date`, other messages by `visibility`.
- Also implemented (1.1.0): attachments (`GET core/…/medias/url` → {url, sig, payload}, then a multipart POST to that url,
  https on an edumoov/educartable host only, fields model `Interaction`, key = the comment id, sig, payload, file; a comment
  of files only says `Pièce(s) jointe(s) :`; a new message's files go in its first comment) through Home Assistant
  (`/api/educartable/upload/{entry}` gives tokens, or paths under `allowlist_external_dirs`), and translation
  (`translate.translate` RPC {text: [title, body], source fr, target}).
- Not in the portal's family app, so not planned: the pupil's skills (only the livret), online exercises.
- New card or visual rework: **propose design options to choose from** before implementing.

## README layout
- Keep the **Marketplace** install section (badge/button, "Settings → Marketplace → Add from link",
  `/local/community/` resources) and the **Buy Me a Coffee** link; the public description must not
  mention the author's city.
- The README is consumed by the **homeassistant-projects** showcase site at build — keep its structure intact.

## Source layout
- The card and the panel are written as ES modules in `src/educartable-card/` and `src/educartable-panel/` (entry
  `index.js`, translations one file per language in `src/educartable-card/i18n/`). `scripts/build-frontend.mjs`
  assembles each into `custom_components/educartable/frontend/<stem>.js` (scripts/bundle.mjs, needs acorn); those
  files are build output, git-ignored and **not committed** — build before pytest, the screenshots or
  `scripts/split-frontend.mjs`. `educartable-badge.js` stays committed as it is.
- The modules share one scope once assembled (a classic script): keep top-level names unique across them. A new module
  must be listed in its `index.js`, in load order.

## Screenshots — do not edit or commit them by hand
The Screenshots workflow (`scripts/screenshots.py`) regenerates them on the PR branch and commits them as the
`juju35-screenshots[bot]` GitHub App. Comparison is exact. English, light/dark twins, neutral mock data, never real
family names; one GIF per distinct animation.

## Translations
- English is the source. Keep every language in sync when a user-facing string changes.
- Languages to keep in sync: en, fr, de, es, it, nl, pt, pl, sr, sr-Latn, ro, da, sv, bg, ru, uk, hu, sk, cs, sl, lv, el (no Irish or Maltese).
- Integration strings: `custom_components/educartable/translations/*.json` (all languages).
- Card UI strings are split per language by `scripts/i18n-split.mjs`; the non-English outputs are generated — **do not
  hand-edit them**; a CI check fails if the split is stale.

## Conventions
- Prefer YAML over UI configuration; keep configurations minimal; test iteratively.
- Keep `ha-*` repos **independent**: no shared/factored code across repos — duplication is fine.
- Call it the **Marketplace** (Home Assistant 2026.11), not HACS, in docs, issue comments and user replies.
- Reply to GitHub issues in the **language of the issue / reporter**, not French by default.
