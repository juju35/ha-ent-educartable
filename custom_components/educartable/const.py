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
API_LIVRET: Final = f"{API_BASE}/livret"
API_CORE: Final = f"{API_BASE}/core"
# Surveys and appointments go through the portal's RPC API: POST {RPC_BASE}/<method> with {params, payload}.
RPC_BASE: Final = "https://api.edumoov.com/rpc"

# The unified "message" object is discriminated by its `type`.
LESSON_TYPES: Final = ("lesson",)  # homework / cahier de textes (per pupil)
ACTIVITY_TYPES: Final = ("activity",)  # cahier de vie: the class's posts (photos, likes, comments)
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
ACTIVITIES_KEPT: Final = 12
NOTIFICATIONS_KEPT: Final = 20
# The appointments booked ahead, as the portal's app lists them ("my next appointments").
APPOINTMENT_DAYS: Final = 92
DOCUMENTS_KEPT: Final = 30

SERVICE_REFRESH: Final = "refresh"
SERVICE_SIGN: Final = "sign"
SERVICE_MARK_READ: Final = "mark_read"
SERVICE_REPLY: Final = "reply"
SERVICE_WRITE: Final = "write_message"
SERVICE_ANSWER_SURVEY: Final = "answer_survey"
SERVICE_BOOK: Final = "book_appointment"
SERVICE_CANCEL_BOOKING: Final = "cancel_appointment"
SERVICE_SIGN_DOCUMENT: Final = "sign_document"
SERVICE_LIKE: Final = "like_activity"
SERVICE_READ_NOTIFICATIONS: Final = "mark_notifications_read"
SERVICE_DELETE_COMMENT: Final = "delete_comment"
ATTR_CONFIG_ENTRY_ID: Final = "config_entry_id"
ATTR_MESSAGE_ID: Final = "message_id"
ATTR_NAME: Final = "name"
ATTR_TEXT: Final = "text"
ATTR_TITLE: Final = "title"
ATTR_CHILDREN: Final = "children"
ATTR_CHILD_ID: Final = "child_id"
ATTR_ANSWERS: Final = "answers"
ATTR_SLOT_ID: Final = "slot_id"
ATTR_DOCUMENT_ID: Final = "document_id"
ATTR_ACTIVITY_ID: Final = "activity_id"
ATTR_LIKED: Final = "liked"
ATTR_NOTIFICATION_ID: Final = "notification_id"
ATTR_COMMENT_ID: Final = "comment_id"
ATTR_ATTACHMENTS: Final = "attachments"
# The panel's uploads waiting to be sent (hass.data key).
UPLOADS: Final = f"{DOMAIN}_uploads"

# Fired on the bus for what appeared since the last update (never on the first one).
EVENT_NEW_HOMEWORK: Final = f"{DOMAIN}_new_homework"
EVENT_NEW_MESSAGE: Final = f"{DOMAIN}_new_message"
EVENT_NEW_NEWS: Final = f"{DOMAIN}_new_news"
EVENT_NEW_DOCUMENT: Final = f"{DOMAIN}_new_document"
EVENT_NEW_ACTIVITY: Final = f"{DOMAIN}_new_activity"

CONF_SHOW_PANEL: Final = "show_panel"
DEFAULT_SHOW_PANEL: Final = True
# Tabs of the panel (and sections of its home page) shown; Home and Settings always are.
CONF_PANEL_TABS: Final = "panel_tabs"
PANEL_TABS: Final = ("homework", "words", "news", "activities", "documents")
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
