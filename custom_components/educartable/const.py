"""Constants for the Educartable integration."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "educartable"

# Unofficial API, reverse-engineered from the mobile web app — it can change without notice.
ACCOUNTS_BASE: Final = "https://accounts.edumoov.com/auth/realms/edumoov"
TOKEN_URL: Final = f"{ACCOUNTS_BASE}/protocol/openid-connect/token"
CLIENT_ID: Final = "educlasse"
SCOPE: Final = "openid"

API_BASE: Final = "https://app.educartable.com/api/1.0"
API_EDUCORE: Final = f"{API_BASE}/educore"
API_EDUCARTABLE: Final = f"{API_BASE}/educartable"

# The unified "message" object is discriminated by its `type`.
LESSON_TYPES: Final = ("lesson", "activity")  # homework / cahier de textes (per pupil)
CARNET_TYPES: Final = ("info", "alert")  # liaison book (to sign)
NEWS_TYPES: Final = ("event", "advert", "meeting")  # news / events / parent meetings

# Names of secrets.yaml entries holding the credentials, read again at every update (instead of storing them).
CONF_PASSWORD_SECRET: Final = "password_secret"
CONF_USERNAME_SECRET: Final = "username_secret"
SECRETS_FILE: Final = "secrets.yaml"

CONF_SCAN_INTERVAL: Final = "scan_interval"
# Notify actions (notify.mobile_app_…) told about new homework, liaison-book messages and news.
CONF_NOTIFY: Final = "notify_services"
CONF_HOMEWORK_DAYS: Final = "homework_days"

# The ENT is a school server shared by many families: never poll it faster than every 10 minutes.
DEFAULT_SCAN_INTERVAL: Final = 30
MIN_SCAN_INTERVAL: Final = 10
DEFAULT_HOMEWORK_DAYS: Final = 14

# Items kept in the attributes: enough for a card, small enough for the state machine.
MESSAGES_KEPT: Final = 10
NEWS_KEPT: Final = 5

SERVICE_REFRESH: Final = "refresh"
SERVICE_SIGN: Final = "sign"
SERVICE_MARK_READ: Final = "mark_read"
ATTR_CONFIG_ENTRY_ID: Final = "config_entry_id"
ATTR_MESSAGE_ID: Final = "message_id"
ATTR_NAME: Final = "name"

# Fired on the bus for what appeared since the last update (never on the first one).
EVENT_NEW_HOMEWORK: Final = f"{DOMAIN}_new_homework"
EVENT_NEW_MESSAGE: Final = f"{DOMAIN}_new_message"
EVENT_NEW_NEWS: Final = f"{DOMAIN}_new_news"

CONF_SHOW_PANEL: Final = "show_panel"
DEFAULT_SHOW_PANEL: Final = True
# Tabs of the panel (and sections of its home page) shown; Home and Settings always are.
CONF_PANEL_TABS: Final = "panel_tabs"
PANEL_TABS: Final = ("homework", "words", "news")
# Who the panel's top bar (the illustrated header) is hidden for; the tabs stay.
CONF_HIDE_HEADER: Final = "hide_header"
HIDE_HEADER_OFF: Final = "off"
HIDE_HEADER_CHOICES: Final = (HIDE_HEADER_OFF, "all", "non_admin")

FRONTEND_URL: Final = "/educartable_static"
CARD_FILENAME: Final = "educartable-card.js"
PANEL_FILENAME: Final = "educartable-panel.js"
BADGE_FILENAME: Final = "educartable-badge.js"
PANEL_ICON: Final = "mdi:book-open-variant"
PANEL_URL_PATH: Final = "educartable"
