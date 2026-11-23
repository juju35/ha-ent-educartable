# Changelog

## 0.1.0 - 2026-11-23

### Features
- First read-only release. Signs in to the Educartable family portal (OpenID Connect, with optional two-factor code; credentials can live in `secrets.yaml`) and exposes, for every account:
  - one device per child with a **Homework to do** sensor (count + the homework in its attributes),
  - a **Liaison book to sign** sensor (count of messages still to sign, across all children),
  - a **News** sensor (recent news, events and parent meetings).
- A `educartable.refresh` action to fetch the latest data on demand.
