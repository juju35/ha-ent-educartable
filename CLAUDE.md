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
pre-commit run -a
vulture custom_components .vulture_whitelist.py --min-confidence 60
npx --yes jscpd@5.4.2 .
pytest
```

## Releasing — how it works here
A release is **automatic**: on push to `main`, if `manifest.json` carries a version with
no matching tag, the Release workflow publishes `vX.Y.Z`. **Never create a tag by hand.**

The `Version consistency` check (validate.yml) requires the **same version** in
`manifest.json` and the top `CHANGELOG.md` entry, or the release fails.

## Bumping the version
This is an **INTEGRATION** repo. A bump is complete only when **both** files below carry the
new version, updated together in one commit:
1. `CHANGELOG.md` → add a "## X.Y.Z - YYYY-MM-DD" section at the top (`### Features` | `Fixes` | `Performance` | `Maintenance`).
2. `custom_components/educartable/manifest.json` → `"version": "X.Y.Z"`.
- Bump rule: `fix` → patch, `feat` → minor, breaking change → major.
- The PR/commit title carries the version in parentheses, e.g. `feat: new sensor (X.Y.Z)`.

## Scope and roadmap
- Educartable is **EDUMOOV**'s family portal for primary school — an unofficial, reverse-engineered
  API (`app.educartable.com`, OpenID Connect on `accounts.edumoov.com`, client `educlasse`). It may
  change without notice.
- This release is **read-only**, two sides: **Élèves** (homework per child) and **Parents**
  (liaison book to sign, news).
- Not yet implemented, pending a network capture on a real parent account: the writes (sign the
  liaison book, mark homework done, reply, answer a survey), attachment URLs, and the pupil
  **livret / compétences** endpoint. A Lovelace card and a sidebar panel are planned.
- New card or visual rework: **propose design options to choose from** before implementing.

## README layout
- Keep the **Marketplace** install section (badge/button, "Settings → Marketplace → Add from link",
  `/local/community/` resources) and the **Buy Me a Coffee** link; the public description must not
  mention the author's city.
- The README is consumed by the **homeassistant-projects** showcase site at build — keep its structure intact.

## Translations
- English is the source. Keep every language in sync when a user-facing string changes.
- Languages to keep in sync: en, fr, de, es, it, nl, pt, pl, sr, sr-Latn, ro, da, sv, bg, ru, uk, hu, sk, cs, sl, lv, el (no Irish or Maltese).
- Integration strings: `custom_components/educartable/translations/*.json` (all languages).

## Conventions
- Prefer YAML over UI configuration; keep configurations minimal; test iteratively.
- Keep `ha-*` repos **independent**: no shared/factored code across repos — duplication is fine.
- Call it the **Marketplace** (Home Assistant 2026.11), not HACS, in docs, issue comments and user replies.
- Reply to GitHub issues in the **language of the issue / reporter**, not French by default.
