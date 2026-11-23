# Educartable for Home Assistant

[![Marketplace](https://img.shields.io/badge/Marketplace-Add%20from%20link-41BDF5)](https://my.home-assistant.io/redirect/hacs_repository/?owner=juju35&repository=ha-ent-educartable&category=integration)
[![Release](https://img.shields.io/github/v/release/juju35/ha-ent-educartable)](https://github.com/juju35/ha-ent-educartable/releases)
[![License](https://img.shields.io/github/license/juju35/ha-ent-educartable)](LICENSE)

A read-only Home Assistant integration for the **Educartable** family portal (EDUMOOV), the digital
workspace of many French primary schools. Sign in with your family account and follow, from Home Assistant:

- **Per child** — a device with a **Homework to do** sensor (count, with the homework in its attributes).
- **For the family** — a **Liaison book to sign** sensor (how many messages still need signing, across all
  children) and a **News** sensor (recent news, events and parent meetings).
- A `educartable.refresh` action to fetch the latest data on demand.

> Unofficial integration, not affiliated with EDUMOOV or Educartable. It relies on the portal's internal API
> and may break if that changes.

## Supported integrations

This integration talks directly to the EDUMOOV family portal, so it needs no other Home Assistant integration:

- [Educartable — portail familles](https://www.educartable.com/) (EDUMOOV)

## Installation

Via the Home Assistant **Marketplace** (2026.11+):

1. In Home Assistant, go to **Settings → Marketplace → Add from link**.
2. Paste `https://github.com/juju35/ha-ent-educartable` and add it as an **integration**.
3. Download it, restart Home Assistant, then add **Educartable** from **Settings → Devices & services**.

## Configuration

Add the integration from the UI and enter the username (often your email) and password given by the school.
If your account uses two-factor authentication, enter the current one-time code as well.

To keep the credentials out of the config entry, leave the username/password fields empty and give the name of
a `secrets.yaml` entry instead — it is read again at every update, so after a password change editing the secret
is enough.

Options (**Settings → Devices & services → Educartable → Configure**):

- **Update interval** — Educartable is shared by the whole school, so 10 minutes is the minimum.
- **Homework window** — homework due within this many days is shown.

## Roadmap

Planned once validated on a real parent account: signing the liaison book, marking homework done, replying to
messages, answering surveys, attachment downloads and the pupil *livret / compétences*, plus a Lovelace card and
a sidebar panel.

## Support

If this is useful to you, you can [buy me a coffee](https://www.buymeacoffee.com/juju35). Issues and ideas are
welcome on the [issue tracker](https://github.com/juju35/ha-ent-educartable/issues).
