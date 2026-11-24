"""Render the Educartable cards and panel with mock data and save the README screenshots.

Usage: python scripts/screenshots.py  (needs `pip install playwright pillow` and `playwright install chromium`;
CHROMIUM_PATH=/path/to/chrome to use another browser)
A screenshot is rewritten only when its decoded pixels change, so a re-render never commits identical images.
The clock is frozen on Monday 16 November 2026 in Paris, so relative days stay the same. Names are made up.
"""

import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FRONTEND = ROOT / "custom_components/educartable/frontend"
# The card and panel files are assembled from their ES modules in src/ (build output, not committed).
subprocess.run(["node", "scripts/build-frontend.mjs"], cwd=ROOT, check=True)
CARD_JS = (FRONTEND / "educartable-card.js").read_text()
PANEL_JS = (FRONTEND / "educartable-panel.js").read_text()
# The panda pictogram of the sidebar entry, taken from the icon set so the mock sidebar shows the real icon.
# The panel's sidebar icon (mdi:book-open-variant).
BOOK = re.search(r"EDUCARTABLE_ICON_PATH = '([^']*)'", CARD_JS).group(1)
NOW = "2026-11-16T09:00:00+01:00"
WIDTH = 460

THEMES = {
    "light": {
        "--primary-background-color": "#e8eaed",
        "--secondary-background-color": "#ececec",
        "--card-background-color": "#ffffff",
        "--primary-text-color": "#212121",
        "--secondary-text-color": "#727272",
        "--divider-color": "rgba(0,0,0,.12)",
    },
    "dark": {
        "--primary-background-color": "#111111",
        "--secondary-background-color": "#282828",
        "--card-background-color": "#1c1c1c",
        "--primary-text-color": "#e1e1e1",
        "--secondary-text-color": "#9b9b9b",
        "--divider-color": "rgba(225,225,225,.12)",
    },
}
COMMON = {
    "--primary-color": "#03a9f4",
    "--info-color": "#039be5",
    "--success-color": "#43a047",
    "--warning-color": "#ffa600",
    "--error-color": "#db4437",
    "--disabled-text-color": "#9e9e9e",
    "--text-primary-color": "#ffffff",
}

# Material Design Icons used by the cards and the panel (@mdi/js).
ICONS = {
    "image-outline": "M19,19H5V5H19M19,3H5A2,2 0 0,0 3,5V19A2,2 0 0,0 5,21H19A2,2 0 0,0 21,19V5A2,2 0 0,0 19,3M13.96,12.29L11.21,15.83L9.25,13.47L6.5,17H17.5L13.96,12.29Z",
    "chevron-down": "M7.41,8.58L12,13.17L16.59,8.58L18,10L12,16L6,10L7.41,8.58Z",
    "close": "M19,6.41L17.59,5L12,10.59L6.41,5L5,6.41L10.59,12L5,17.59L6.41,19L12,13.41L17.59,19L19,17.59L13.41,12L19,6.41Z",
    "school-outline": "M12 3L1 9L5 11.18V17.18L12 21L19 17.18V11.18L21 10.09V17H23V9L12 3M18.82 9L12 12.72L5.18 9L12 5.28L18.82 9M17 16L12 18.72L7 16V12.27L12 15L17 12.27V16Z",
    "email-outline": "M22 6C22 4.9 21.1 4 20 4H4C2.9 4 2 4.9 2 6V18C2 19.1 2.9 20 4 20H20C21.1 20 22 19.1 22 18V6M20 6L12 11L4 6H20M20 18H4V8L12 13L20 8V18Z",
    "notebook-edit-outline": "M19.07 14.88L21.12 16.93L15.06 23H13V20.94L19.07 14.88M21.04 13.13C21.18 13.13 21.31 13.19 21.42 13.3L22.7 14.58C22.92 14.79 22.92 15.14 22.7 15.35L21.7 16.35L19.65 14.3L20.65 13.3C20.76 13.19 20.9 13.13 21.04 13.13M17 4V10L15 8L13 10V4H9V20H11V22H7C5.95 22 5 21.05 5 20V19H3V17H5V13H3V11H5V7H3V5H5V4C5 2.89 5.9 2 7 2H19C20.05 2 21 2.95 21 4V10L19 12V4H17M5 5V7H7V5H5M5 11V13H7V11H5M5 17V19H7V17H5Z",
    "pencil-outline": "M14.06,9L15,9.94L5.92,19H5V18.08L14.06,9M17.66,3C17.41,3 17.15,3.1 16.96,3.29L15.13,5.12L18.88,8.87L20.71,7.04C21.1,6.65 21.1,6 20.71,5.63L18.37,3.29C18.17,3.09 17.92,3 17.66,3M14.06,6.19L3,17.25V21H6.75L17.81,9.94L14.06,6.19Z",
    "refresh": "M17.65,6.35C16.2,4.9 14.21,4 12,4A8,8 0 0,0 4,12A8,8 0 0,0 12,20C15.73,20 18.84,17.45 19.73,14H17.65C16.83,16.33 14.61,18 12,18A6,6 0 0,1 6,12A6,6 0 0,1 12,6C13.66,6 15.14,6.69 16.22,7.78L13,11H20V4L17.65,6.35Z",
    "open-in-new": "M14,3V5H17.59L7.76,14.83L9.17,16.24L19,6.41V10H21V3M19,19H5V5H12V3H5C3.89,3 3,3.9 3,5V19A2,2 0 0,0 5,21H19A2,2 0 0,0 21,19V12H19V19Z",
    "check-circle-outline": "M12 2C6.5 2 2 6.5 2 12S6.5 22 12 22 22 17.5 22 12 17.5 2 12 2M12 20C7.59 20 4 16.41 4 12S7.59 4 12 4 20 7.59 20 12 16.41 20 12 20M16.59 7.58L10 14.17L7.41 11.59L6 13L10 17L18 9L16.59 7.58Z",
    "checkbox-marked-outline": "M19,19H5V5H15V3H5C3.89,3 3,3.89 3,5V19A2,2 0 0,0 5,21H19A2,2 0 0,0 21,19V11H19M7.91,10.08L6.5,11.5L11,16L21,6L19.59,4.58L11,13.17L7.91,10.08Z",
    "checkbox-blank-outline": "M19,3H5C3.89,3 3,3.89 3,5V19A2,2 0 0,0 5,21H19A2,2 0 0,0 21,19V5C21,3.89 20.1,3 19,3M19,5V19H5V5H19Z",
    "email-open-outline": "M21.03 6.29L12 .64L2.97 6.29C2.39 6.64 2 7.27 2 8V18C2 19.1 2.9 20 4 20H20C21.1 20 22 19.1 22 18V8C22 7.27 21.61 6.64 21.03 6.29M20 18H4V10L12 15L20 10V18M12 13L4 8L12 3L20 8L12 13Z",
    "paperclip": "M16.5,6V17.5A4,4 0 0,1 12.5,21.5A4,4 0 0,1 8.5,17.5V5A2.5,2.5 0 0,1 11,2.5A2.5,2.5 0 0,1 13.5,5V15.5A1,1 0 0,1 12.5,16.5A1,1 0 0,1 11.5,15.5V6H10V15.5A2.5,2.5 0 0,0 12.5,18A2.5,2.5 0 0,0 15,15.5V5A4,4 0 0,0 11,1A4,4 0 0,0 7,5V17.5A5.5,5.5 0 0,0 12.5,23A5.5,5.5 0 0,0 18,17.5V6H16.5Z",
    "newspaper-variant-outline": "M20 5L20 19L4 19L4 5H20M20 3H4C2.89 3 2 3.89 2 5V19C2 20.11 2.89 21 4 21H20C21.11 21 22 20.11 22 19V5C22 3.89 21.11 3 20 3M18 15H6V17H18V15M10 7H6V13H10V7M12 9H18V7H12V9M18 11H12V13H18V11Z",
    "calendar-blank-outline": "M19 3H18V1H16V3H8V1H6V3H5C3.89 3 3 3.9 3 5V19C3 20.11 3.9 21 5 21H19C20.11 21 21 20.11 21 19V5C21 3.9 20.11 3 19 3M19 19H5V9H19V19M19 7H5V5H19V7Z",
    "arrow-expand": "M10,21V19H6.41L10.91,14.5L9.5,13.09L5,17.59V14H3V21H10M14.5,10.91L19,6.41V10H21V3H14V5H17.59L13.09,9.5L14.5,10.91Z",
    "arrow-collapse": "M19.5,3.09L15,7.59V4H13V11H20V9H16.41L20.91,4.5L19.5,3.09M4,13V15H7.59L3.09,19.5L4.5,20.91L9,16.41V20H11V13H4Z",
    "menu": "M3,6H21V8H3V6M3,11H21V13H3V11M3,16H21V18H3V16Z",
    "arrow-left": "M20,11V13H8L13.5,18.5L12.08,19.92L4.16,12L12.08,4.08L13.5,5.5L8,11H20Z",
    "file-pdf-box": "M19 3H5C3.9 3 3 3.9 3 5V19C3 20.1 3.9 21 5 21H19C20.1 21 21 20.1 21 19V5C21 3.9 20.1 3 19 3M9.5 11.5C9.5 12.3 8.8 13 8 13H7V15H5.5V9H8C8.8 9 9.5 9.7 9.5 10.5V11.5M14.5 13.5C14.5 14.3 13.8 15 13 15H10.5V9H13C13.8 9 14.5 9.7 14.5 10.5V13.5M18.5 10.5H17V11.5H18.5V13H17V15H15.5V9H18.5V10.5M12 10.5H13V13.5H12V10.5M7 10.5H8V11.5H7V10.5Z",
    "notebook-outline": "M19 2C20.11 2 21 2.9 21 4V20C21 21.11 20.11 22 19 22H7C5.89 22 5 21.11 5 20V19H3V17H5V13H3V11H5V7H3V5H5V4C5 2.89 5.89 2 7 2H19M19 20V4H7V5H9V7H7V11H9V13H7V17H9V19H7V20H19Z",
    "download": "M5,20H19V18H5M19,9H15V3H9V9H5L12,16L19,9Z",
    "post-outline": "M19 5V19H5V5H19M21 3H3V21H21V3M17 17H7V16H17V17M17 15H7V14H17V15M17 12H7V7H17V12Z",
    "calendar-star": "M19,19H5V8H19M16,1V3H8V1H6V3H5C3.89,3 3,3.89 3,5V19A2,2 0 0,0 5,21H19A2,2 0 0,0 21,19V5C21,3.89 20.1,3 19,3H18V1M10.88,12H7.27L10.19,14.11L9.08,17.56L12,15.43L14.92,17.56L13.8,14.12L16.72,12H13.12L12,8.56L10.88,12Z",
    "account-group-outline": "M12,5A3.5,3.5 0 0,0 8.5,8.5A3.5,3.5 0 0,0 12,12A3.5,3.5 0 0,0 15.5,8.5A3.5,3.5 0 0,0 12,5M12,7A1.5,1.5 0 0,1 13.5,8.5A1.5,1.5 0 0,1 12,10A1.5,1.5 0 0,1 10.5,8.5A1.5,1.5 0 0,1 12,7M5.5,8A2.5,2.5 0 0,0 3,10.5C3,11.44 3.53,12.25 4.29,12.68C4.65,12.88 5.06,13 5.5,13C5.94,13 6.35,12.88 6.71,12.68C7.08,12.47 7.39,12.17 7.62,11.81C6.89,10.86 6.5,9.7 6.5,8.5C6.5,8.41 6.5,8.31 6.5,8.22C6.2,8.08 5.86,8 5.5,8M18.5,8C18.14,8 17.8,8.08 17.5,8.22C17.5,8.31 17.5,8.41 17.5,8.5C17.5,9.7 17.11,10.86 16.38,11.81C16.5,12 16.63,12.15 16.78,12.3C16.94,12.45 17.1,12.58 17.29,12.68C17.65,12.88 18.06,13 18.5,13C18.94,13 19.35,12.88 19.71,12.68C20.47,12.25 21,11.44 21,10.5A2.5,2.5 0 0,0 18.5,8M12,14C9.66,14 5,15.17 5,17.5V19H19V17.5C19,15.17 14.34,14 12,14M4.71,14.55C2.78,14.78 0,15.76 0,17.5V19H3V17.07C3,16.06 3.69,15.22 4.71,14.55M19.29,14.55C20.31,15.22 21,16.06 21,17.07V19H24V17.5C24,15.76 21.22,14.78 19.29,14.55M12,16C13.53,16 15.24,16.5 16.23,17H7.77C8.76,16.5 10.47,16 12,16Z",
    "home-outline": "M12 5.69L17 10.19V18H15V12H9V18H7V10.19L12 5.69M12 3L2 12H5V20H11V14H13V20H19V12H22",
    "cog": "M12,15.5A3.5,3.5 0 0,1 8.5,12A3.5,3.5 0 0,1 12,8.5A3.5,3.5 0 0,1 15.5,12A3.5,3.5 0 0,1 12,15.5M19.43,12.97C19.47,12.65 19.5,12.33 19.5,12C19.5,11.67 19.47,11.34 19.43,11L21.54,9.37C21.73,9.22 21.78,8.95 21.66,8.73L19.66,5.27C19.54,5.05 19.27,4.96 19.05,5.05L16.56,6.05C16.04,5.66 15.5,5.32 14.87,5.07L14.5,2.42C14.46,2.18 14.25,2 14,2H10C9.75,2 9.54,2.18 9.5,2.42L9.13,5.07C8.5,5.32 7.96,5.66 7.44,6.05L4.95,5.05C4.73,4.96 4.46,5.05 4.34,5.27L2.34,8.73C2.21,8.95 2.27,9.22 2.46,9.37L4.57,11C4.53,11.34 4.5,11.67 4.5,12C4.5,12.33 4.53,12.65 4.57,12.97L2.46,14.63C2.27,14.78 2.21,15.05 2.34,15.27L4.34,18.73C4.46,18.95 4.73,19.03 4.95,18.95L7.44,17.94C7.96,18.34 8.5,18.68 9.13,18.93L9.5,21.58C9.54,21.82 9.75,22 10,22H14C14.25,22 14.46,21.82 14.5,21.58L14.87,18.93C15.5,18.67 16.04,18.34 16.56,17.94L19.05,18.95C19.27,19.03 19.54,18.95 19.66,18.73L21.66,15.27C21.78,15.05 21.73,14.78 21.54,14.63L19.43,12.97Z",
    "comment-outline": "M9,22A1,1 0 0,1 8,21V18H4A2,2 0 0,1 2,16V4C2,2.89 2.9,2 4,2H20A2,2 0 0,1 22,4V16A2,2 0 0,1 20,18H13.9L10.2,21.71C10,21.9 9.75,22 9.5,22V22H9M10,16V19.08L13.08,16H20V4H4V16H10Z",
}

# Generic Material icons for the other rows of the mock Home Assistant sidebar.
SIDEBAR_ICONS = {
    "home": "M10,20V14H14V20H19V12H22L12,3L2,12H5V20H10Z",
    "cog": "M12,15.5A3.5,3.5 0 0,1 8.5,12A3.5,3.5 0 0,1 12,8.5A3.5,3.5 0 0,1 15.5,12A3.5,3.5 0 0,1 12,15.5M19.43,12.98C19.47,12.66 19.5,12.33 19.5,12C19.5,11.67 19.47,11.34 19.43,11L21.54,9.37C21.73,9.22 21.78,8.95 21.66,8.73L19.66,5.27C19.54,5.05 19.27,4.96 19.05,5.05L16.56,6.05C16.04,5.66 15.5,5.32 14.87,5.07L14.5,2.42C14.46,2.18 14.25,2 14,2H10C9.75,2 9.54,2.18 9.5,2.42L9.13,5.07C8.5,5.32 7.96,5.66 7.44,6.05L4.95,5.05C4.73,4.96 4.46,5.05 4.34,5.27L2.34,8.73C2.21,8.95 2.27,9.22 2.46,9.37L4.57,11C4.53,11.34 4.5,11.67 4.5,12C4.5,12.33 4.53,12.66 4.57,12.98L2.46,14.63C2.27,14.78 2.21,15.05 2.34,15.27L4.34,18.73C4.46,18.95 4.73,19.03 4.95,18.95L7.44,17.94C7.96,18.34 8.5,18.68 9.13,18.93L9.5,21.58C9.54,21.82 9.75,22 10,22H14C14.25,22 14.46,21.82 14.5,21.58L14.87,18.93C15.5,18.67 16.04,18.34 16.56,17.94L19.05,18.95C19.27,19.03 19.54,18.95 19.66,18.73L21.66,15.27C21.78,15.05 21.73,14.78 21.54,14.63L19.43,12.98Z",
    "bell": "M21,19V20H3V19L5,17V11C5,7.9 7.03,5.17 10,4.29C10,4.19 10,4.1 10,4A2,2 0 0,1 12,2A2,2 0 0,1 14,4C14,4.1 14,4.19 14,4.29C16.97,5.17 19,7.9 19,11V17L21,19M14,21A2,2 0 0,1 12,23A2,2 0 0,1 10,21H14Z",
}


def _sidebar_row(icon, label, *, active=False, badge=None, badge_color="var(--primary-color)"):
    text = "var(--primary-color)" if active else "var(--secondary-text-color)"
    bg = "background:rgba(3,169,244,.12);" if active else ""
    weight = "font-weight:500;" if active else ""
    badge_html = (
        f'<span style="min-width:18px;height:18px;box-sizing:border-box;padding:0 5px;display:inline-flex;'
        f"align-items:center;justify-content:center;border-radius:9px;font-size:11px;font-weight:500;line-height:1;"
        f'color:#fff;background:{badge_color};">{badge}</span>'
        if badge is not None
        else ""
    )
    return (
        f'<div style="display:flex;align-items:center;height:48px;color:{text};{bg}'
        f'border-left:3px solid {"var(--primary-color)" if active else "transparent"};">'
        f'<svg viewBox="0 0 24 24" style="width:24px;height:24px;margin:0 12px 0 9px;fill:currentColor;flex:none;">'
        f'<path d="{icon}"/></svg>'
        f'<span style="flex:1;font-size:14px;{weight}">{label}</span>'
        f"{badge_html}"
        '<span style="width:12px;flex:none;"></span></div>'
    )


def sidebar_html(count):
    """A faithful mock of the Home Assistant sidebar: the Educartable entry shows its panda icon and the badge, at the end
    of the row like the Notifications count below it."""
    rows = [
        _sidebar_row(SIDEBAR_ICONS["home"], "Overview"),
        _sidebar_row(ICONS["calendar-blank-outline"], "Calendar"),
        _sidebar_row(BOOK, "Educartable", active=True, badge=count),
        _sidebar_row(SIDEBAR_ICONS["cog"], "Settings"),
        _sidebar_row(SIDEBAR_ICONS["bell"], "Notifications", badge=3, badge_color="#ff9800"),
    ]
    return (
        '<div style="width:255px;background:var(--card-background-color);'
        'border-right:1px solid var(--divider-color);padding:8px 0;">' + "".join(rows) + "</div>"
    )


# What the signed file URLs show: a drawn map for images, a page of text for PDFs (mock content).
HA_ELEMENTS = """
const ICONS = %s;
customElements.define("ha-card", class extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" }).innerHTML =
      "<style>:host{display:block;background:var(--card-background-color);border-radius:12px;" +
      "border:1px solid var(--divider-color);color:var(--primary-text-color);overflow:hidden}</style><slot></slot>";
  }
});
customElements.define("ha-icon", class extends HTMLElement {
  connectedCallback() {
    const path = ICONS[(this.getAttribute("icon") || "").replace("mdi:", "")] || "";
    this.style.display = "inline-flex";
    this.innerHTML = '<svg viewBox="0 0 24 24" style="width:var(--mdc-icon-size,24px);height:var(--mdc-icon-size,24px);fill:currentColor"><path d="' + path + '"/></svg>';
  }
});
customElements.define("ha-menu-button", class extends HTMLElement {
  connectedCallback() { this.style.cssText = "display:none"; }
});
customElements.define("ha-icon-button", class extends HTMLElement {
  connectedCallback() {
    this.style.cssText = "display:inline-flex;align-items:center;justify-content:center;width:40px;height:40px;color:var(--secondary-text-color)";
  }
});
""" % json.dumps(ICONS)  # noqa: UP031 - percent-format keeps the embedded JS braces un-escaped


# Mock data, neutral names only. Dates are relative to NOW (Monday 16 November 2026).
CHILDREN = [
    {
        "id": "p1",
        "firstname": "Alex",
        "name": "Alex Martin",
        "classroom": "Year 3 A",
        "teacher": "Ms Brown",
        "grade": "CE2",
    },
    {
        "id": "p2",
        "firstname": "Sam",
        "name": "Sam Martin",
        "classroom": "Year 1 B",
        "teacher": "Mr Green",
        "grade": "CP",
    },
]

CARNET = [
    {
        "id": "101",
        "title": "Museum trip on Friday",
        "type": "info",
        "date": "2026-11-16T07:30:00+01:00",
        "to_sign": True,
    },
    {
        "id": "102",
        "title": "Swimming lessons start",
        "type": "alert",
        "date": "2026-11-12T16:00:00+01:00",
        "to_sign": False,
    },
]

HOMEWORK = {
    "p1": [
        {"id": "h1", "title": "Learn the poem, page 12", "subject": "French", "due": "2026-11-19", "done": False},
        {"id": "h2", "title": "Times table of 7", "subject": "Maths", "due": "2026-11-19", "done": False},
        {"id": "h3", "title": "Read chapter 3", "subject": "French", "due": "2026-11-16", "done": True},
    ],
    "p2": [
        {"id": "h4", "title": "Bring a cardboard box", "subject": "Art", "due": "2026-11-20", "done": False},
    ],
}

NEWS = [
    {"id": "n1", "title": "Christmas fair", "type": "event", "date": "2026-11-15T10:00:00+01:00"},
    {"id": "n2", "title": "Parents' evening", "type": "meeting", "date": "2026-11-13T18:00:00+01:00"},
    {"id": "n3", "title": "Canteen menus for December", "type": "advert", "date": "2026-11-10T09:00:00+01:00"},
]


def _sensor(entity_id, state, **attributes):
    return {
        "entity_id": entity_id,
        "state": str(state),
        "attributes": {"config_entry_id": "mock", **attributes},
    }


def _homework_sensor(child, items):
    todo = sum(1 for h in items if not h["done"])
    entity = f"sensor.{child['firstname'].lower()}_homework_to_do"
    return _sensor(entity, todo, child_id=child["id"], child=child["firstname"], homework=items)


STATES = {
    s["entity_id"]: s
    for s in [
        _sensor("sensor.educartable_liaison_book_to_sign", 1, stale=[], messages=CARNET),
        _sensor("sensor.educartable_news", 3, stale=[], news=NEWS),
        *[_homework_sensor(ch, HOMEWORK[ch["id"]]) for ch in CHILDREN],
        _sensor(
            "sensor.educartable_last_update",
            "2026-11-16T07:58:00+00:00",
            stale=[],
            account={"name": "Parent"},
            children=CHILDREN,
            panel_tabs=["homework", "words", "news"],
            hide_header="off",
        ),
    ]
}

# Everything signed: the header picture shows the homework left (the pen writes).
STATES_SIGNED = {
    **STATES,
    "sensor.educartable_liaison_book_to_sign": _sensor(
        "sensor.educartable_liaison_book_to_sign", 0, stale=[], messages=[{**m, "to_sign": False} for m in CARNET]
    ),
}

# The panel's top bar hidden (Hide the top bar: For everyone): the tabs alone.
STATES_BARE = {
    **STATES,
    "sensor.educartable_last_update": {
        **STATES["sensor.educartable_last_update"],
        "attributes": {**STATES["sensor.educartable_last_update"]["attributes"], "hide_header": "all"},
    },
}

SHOTS = [
    {"file": "card", "theme": "light", "config": {}},
    {"file": "card-dark", "theme": "dark", "config": {}},
    {"file": "mini-card", "theme": "light", "element": "educartable-mini-card", "width": 300, "config": {}},
    {"file": "mini-card-dark", "theme": "dark", "element": "educartable-mini-card", "width": 300, "config": {}},
    # The mini card expanded by its detail button: the full card, at the full card's width.
    {"file": "mini-card-zoom", "theme": "light", "element": "educartable-mini-card", "config": {}, "click": ".detail"},
    {
        "file": "mini-card-zoom-dark",
        "theme": "dark",
        "element": "educartable-mini-card",
        "config": {},
        "click": ".detail",
    },
    {"file": "panel", "theme": "light", "panel": "home", "width": 960},
    {"file": "panel-dark", "theme": "dark", "panel": "home", "width": 960},
    {"file": "panel-bare", "theme": "light", "panel": "home", "width": 960, "states": STATES_BARE},
    {"file": "panel-bare-dark", "theme": "dark", "panel": "home", "width": 960, "states": STATES_BARE},
    {"file": "panel-homework", "theme": "light", "panel": "homework", "width": 960},
    {"file": "panel-homework-dark", "theme": "dark", "panel": "homework", "width": 960},
    {"file": "panel-words", "theme": "light", "panel": "words", "width": 960},
    {"file": "panel-words-dark", "theme": "dark", "panel": "words", "width": 960},
    {"file": "panel-news", "theme": "light", "panel": "news", "width": 960},
    {"file": "panel-news-dark", "theme": "dark", "panel": "news", "width": 960},
    # The sidebar entry with its badge: 1 message to sign + 3 homework = 4, like the mock sensors.
    {"file": "sidebar", "theme": "light", "sidebar": True, "count": 4, "width": 256},
    {"file": "sidebar-dark", "theme": "dark", "sidebar": True, "count": 4, "width": 256},
]


def _frames(path):
    """Decoded RGBA pixels of every frame, with each frame's duration: what the image looks like, not its bytes."""
    from PIL import Image, ImageSequence

    with Image.open(path) as image:
        return [
            (frame.info.get("duration"), frame.convert("RGBA").size, frame.convert("RGBA").tobytes())
            for frame in ImageSequence.Iterator(image)
        ]


def replace_if_changed(new, out):
    """Move the fresh render `new` onto `out` only when its pixels differ (or `out` is missing); return whether
    `out` changed. Encoders do not give the same bytes twice for the same image, which made the screenshots
    workflow commit images that looked exactly the same."""
    new, out = Path(new), Path(out)
    if out.exists() and _frames(new) == _frames(out):
        new.unlink()
        return False
    shutil.move(str(new), str(out))
    return True


# Pauses every animation at `t` ms and returns how many it paused. document.getAnimations() leaves out shadow trees,
# where the card's spinner lives: it kept turning in real time and each run gave other GIF frames.
PAUSE_ANIMATIONS = """(t) => {
  const all = (root) => [
    ...root.getAnimations(),
    ...[...root.querySelectorAll("*")].filter((el) => el.shadowRoot).flatMap((el) => all(el.shadowRoot)),
  ];
  const animations = all(document);
  for (const a of animations) { a.pause(); a.currentTime = t; }
  return animations.length;
}"""


def page_html(theme, width=WIDTH, panel=False):
    variables = "".join(f"{k}:{v};" for k, v in {**THEMES[theme], **COMMON}.items())
    padding = 0 if panel else 16
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>
  :root {{ {variables} }}
  body {{ margin: 0; padding: {padding}px; background: var(--primary-background-color); color: var(--primary-text-color);
         font-family: Roboto, "Segoe UI", Helvetica, Arial, sans-serif; width: {width}px; }}
  educartable-panel {{ min-height: 0 !important; }}
</style></head><body><div id="root"></div></body></html>"""


def mount(context, shot):
    # A new page per capture: the files' top-level declarations would clash in a reused page.
    page = context.new_page()
    page.on("pageerror", lambda err, name=shot["file"]: print(f"{name}: page error: {err}"))
    page.clock.set_fixed_time(NOW)
    if shot.get("sidebar"):
        # A static mock of the sidebar: no Home Assistant element, just the rows drawn with the theme's colours.
        page.set_content(page_html(shot["theme"], shot["width"], panel=True))
        page.evaluate("(h) => { document.getElementById('root').innerHTML = h; }", sidebar_html(shot["count"]))
        page.wait_for_timeout(100)
        return page
    if shot.get("panel"):
        # The panel fills the window, as wide as the shot.
        page.set_viewport_size({"width": shot["width"], "height": 2400})
    page.set_content(page_html(shot["theme"], shot.get("width", WIDTH), bool(shot.get("panel"))))
    page.add_script_tag(content=HA_ELEMENTS)
    page.add_script_tag(content=CARD_JS)
    if shot.get("panel"):
        page.add_script_tag(content=PANEL_JS)
    page.evaluate(
        """({config, states, element, tab, dark}) => {
          const hass = {states, themes: {darkMode: dark}, language: "en", locale: {language: "en", time_format: "24"}, user: {is_admin: true},
                        callService: () => Promise.resolve(), callWS: () => Promise.resolve({})};
          const el = document.createElement(element);
          if (tab) {
            el._tab = tab;
            el.panel = {config: {}};
            el.narrow = false;
          } else {
            el.setConfig({type: `custom:${element}`, ...config});
          }
          el.hass = hass;
          document.getElementById("root").appendChild(el);
        }""",
        {
            "config": shot.get("config", {}),
            "states": shot.get("states", STATES),
            "element": "educartable-panel" if shot.get("panel") else shot.get("element", "educartable-card"),
            "tab": shot.get("panel"),
            # The illustrated header follows the dark theme alone, so dark twins show the night.
            "dark": shot["theme"] == "dark",
        },
    )
    if shot.get("click"):
        page.locator(shot["click"]).first.click()
        page.mouse.move(0, 0)
    page.wait_for_timeout(300)
    return page


def capture(page, shot, out, animations="disabled"):
    # Stills disable the animations; a GIF frame keeps them as paused at its time (disabled would reset them).
    width = shot.get("width", WIDTH)
    pad = 0 if shot.get("panel") or shot.get("sidebar") else 32
    if shot.get("crop"):
        # Only one element (the illustrated header), with the page's margin at the top and sides of a card's.
        box = page.locator(shot["crop"]).first.bounding_box()
        m = pad // 2
        # Nothing under it: the card's content starts right below the header.
        clip = {
            "x": box["x"] - m,
            "y": box["y"] - m,
            "width": box["width"] + 2 * m,
            "height": int(box["height"] + 0.999) + m,
        }
        page.screenshot(path=str(out), clip=clip, animations=animations)
        return clip
    box = page.locator("#root").bounding_box()
    clip = {"x": 0, "y": 0, "width": width + pad, "height": int(box["height"] + 0.999) + pad}
    page.screenshot(path=str(out), clip=clip, animations=animations)
    return clip


def animate(context, shot, *, fps=20, seconds=2, refreshing=True):
    """Record an animation as a looping screenshots/<file>.gif (needs ffmpeg): the refresh spinner, or with
    refreshing=False what the page plays by itself (the header's envelope, pen). Every animation is paused and
    stepped frame by frame, so the GIF is identical whatever the machine's speed."""
    page = mount(context, shot)
    if refreshing:
        page.evaluate(
            """() => { const el = document.getElementById("root").firstElementChild; el._refreshing = true; el._render(); }"""
        )
    page.wait_for_timeout(200)
    frames = round(fps * seconds)
    with tempfile.TemporaryDirectory() as frame_dir:
        clip = None
        for i in range(frames):
            page.evaluate(f"(t) => ({PAUSE_ANIMATIONS})(t)", (i * 1000) / fps)
            clip = capture(page, shot, f"{frame_dir}/f{i:03d}.png", animations="allow")
        page.close()
        out = f"{frame_dir}/{shot['file']}.gif"
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-loglevel",
                "error",
                "-framerate",
                str(fps),
                "-i",
                f"{frame_dir}/f%03d.png",
                "-vf",
                f"scale={clip['width']}:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=128[p];[b][p]paletteuse=dither=bayer:bayer_scale=4",
                "-loop",
                "0",
                out,
            ],
            check=True,
        )
        changed = replace_if_changed(out, ROOT / "screenshots" / f"{shot['file']}.gif")
    print(f"screenshots/{shot['file']}.gif" + ("" if changed else " (unchanged)"))


def main():
    out_dir = ROOT / "screenshots"
    out_dir.mkdir(exist_ok=True)
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        chromium = os.environ.get("CHROMIUM_PATH")
        browser = p.chromium.launch(executable_path=chromium) if chromium else p.chromium.launch()
        context = browser.new_context(
            device_scale_factor=2, viewport={"width": 1000, "height": 2400}, timezone_id="Europe/Paris", locale="en-GB"
        )
        for shot in SHOTS:
            page = mount(context, shot)
            page.wait_for_timeout(300)
            with tempfile.TemporaryDirectory() as tmp:
                fresh = Path(tmp) / f"{shot['file']}.png"
                capture(page, shot, fresh)
                changed = replace_if_changed(fresh, out_dir / f"{shot['file']}.png")
            print(f"screenshots/{shot['file']}.png" + ("" if changed else " (unchanged)"))
            page.close()
        # The refresh spinner in both themes: the light GIF gets a -dark twin with the exact same setup.
        for theme, suffix in (("light", ""), ("dark", "-dark")):
            animate(context, {"file": f"refreshing{suffix}", "theme": theme, "config": {}})
        # The illustrated header, one GIF per animation, card and panel, day and night: the liaison book to sign (the
        # envelope bobs, its count blinks: 2 s and 1.6 s, looped over 8 s) and homework left (the pen writes, 1 s).
        headers = (
            ("card-header", {"config": {}, "crop": ".banner"}),
            ("panel-header", {"panel": "home", "width": 960, "crop": ".banner"}),
        )
        for name, base in headers:
            for theme, suffix in (("light", ""), ("dark", "-dark")):
                animate(
                    context,
                    {**base, "file": f"{name}-liaison-book{suffix}", "theme": theme},
                    fps=12.5,
                    seconds=8,
                    refreshing=False,
                )
                animate(
                    context,
                    {**base, "file": f"{name}-homework{suffix}", "theme": theme, "states": STATES_SIGNED},
                    seconds=2,
                    refreshing=False,
                )
        browser.close()


if __name__ == "__main__":
    main()
