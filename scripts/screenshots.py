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
from urllib.parse import quote

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
    "file-certificate-outline": "M14 13V11L12 12L10 11V13L8 14L10 15V17L12 16L14 17V15L16 14M14 2H7A2 2 0 0 0 5 4V18A2 2 0 0 0 7 20H8V18H7V4H13V8H17V18H16V20H17A2 2 0 0 0 19 18V7M14 13V11L12 12L10 11V13L8 14L10 15V17L12 16L14 17V15L16 14M10 23L12 22L14 23V18H10M14 13V11L12 12L10 11V13L8 14L10 15V17L12 16L14 17V15L16 14Z",
    "certificate-outline": "M13 21L15 20L17 21V14H13M17 9V7L15 8L13 7V9L11 10L13 11V13L15 12L17 13V11L19 10M20 3H4A2 2 0 0 0 2 5V15A2 2 0 0 0 4 17H11V15H4V5H20V15H19V17H20A2 2 0 0 0 22 15V5A2 2 0 0 0 20 3M11 8H5V6H11M9 11H5V9H9M11 14H5V12H11Z",
    "file-document-outline": "M6,2A2,2 0 0,0 4,4V20A2,2 0 0,0 6,22H18A2,2 0 0,0 20,20V8L14,2H6M6,4H13V9H18V20H6V4M8,12V14H16V12H8M8,16V18H13V16H8Z",
    "forum-outline": "M15,4V11H5.17L4,12.17V4H15M16,2H3A1,1 0 0,0 2,3V17L6,13H16A1,1 0 0,0 17,12V3A1,1 0 0,0 16,2M21,6H19V15H6V17A1,1 0 0,0 7,18H18L22,22V7A1,1 0 0,0 21,6Z",
    "calendar-clock": "M15,13H16.5V15.82L18.94,17.23L18.19,18.53L15,16.69V13M19,8H5V19H9.67C9.24,18.09 9,17.07 9,16A7,7 0 0,1 16,9C17.07,9 18.09,9.24 19,9.67V8M5,21C3.89,21 3,20.1 3,19V5C3,3.89 3.89,3 5,3H6V1H8V3H16V1H18V3H19A2,2 0 0,1 21,5V11.1C22.24,12.36 23,14.09 23,16A7,7 0 0,1 16,23C14.09,23 12.36,22.24 11.1,21H5M16,11.15A4.85,4.85 0 0,0 11.15,16C11.15,18.68 13.32,20.85 16,20.85A4.85,4.85 0 0,0 20.85,16C20.85,13.32 18.68,11.15 16,11.15Z",
    "calendar-check": "M19,19H5V8H19M19,3H18V1H16V3H8V1H6V3H5C3.89,3 3,3.9 3,5V19A2,2 0 0,0 5,21H19A2,2 0 0,0 21,19V5A2,2 0 0,0 19,3M16.53,11.06L15.47,10L10.59,14.88L8.47,12.76L7.41,13.82L10.59,17L16.53,11.06Z",
    "poll": "M3,22V8H7V22H3M10,22V2H14V22H10M17,22V14H21V22H17Z",
    "email-edit-outline": "M19.07 13.88L13 19.94V22H15.06L21.12 15.93M22.7 13.58L21.42 12.3C21.32 12.19 21.18 12.13 21.04 12.13C20.89 12.14 20.75 12.19 20.65 12.3L19.65 13.3L21.7 15.3L22.7 14.3C22.89 14.1 22.89 13.78 22.7 13.58M11 18H4V8L12 13L20 8V10H22V6C22 4.9 21.1 4 20 4H4C2.9 4 2 4.9 2 6V18C2 19.1 2.9 20 4 20H11V18M20 6L12 11L4 6H20Z",
    "email-alert-outline": "M24 7H22V13H24V7M24 15H22V17H24V15M20 6C20 4.9 19.1 4 18 4H2C.9 4 0 4.9 0 6V18C0 19.1 .9 20 2 20H18C19.1 20 20 19.1 20 18V6M18 6L10 11L2 6H18M18 18H2V8L10 13L18 8V18Z",
    "image-multiple-outline": "M21,17H7V3H21M21,1H7A2,2 0 0,0 5,3V17A2,2 0 0,0 7,19H21A2,2 0 0,0 23,17V3A2,2 0 0,0 21,1M3,5H1V21A2,2 0 0,0 3,23H19V21H3M15.96,10.29L13.21,13.83L11.25,11.47L8.5,15H19.5L15.96,10.29Z",
    "heart": "M12,21.35L10.55,20.03C5.4,15.36 2,12.27 2,8.5C2,5.41 4.42,3 7.5,3C9.24,3 10.91,3.81 12,5.08C13.09,3.81 14.76,3 16.5,3C19.58,3 22,5.41 22,8.5C22,12.27 18.6,15.36 13.45,20.03L12,21.35Z",
    "heart-outline": "M12.1,18.55L12,18.65L11.89,18.55C7.14,14.24 4,11.39 4,8.5C4,6.5 5.5,5 7.5,5C9.04,5 10.54,6 11.07,7.36H12.93C13.46,6 14.96,5 16.5,5C18.5,5 20,6.5 20,8.5C20,11.39 16.86,14.24 12.1,18.55M16.5,3C14.76,3 13.09,3.81 12,5.08C10.91,3.81 9.24,3 7.5,3C4.42,3 2,5.41 2,8.5C2,12.27 5.4,15.36 10.55,20.03L12,21.35L13.45,20.03C18.6,15.36 22,12.27 22,8.5C22,5.41 19.58,3 16.5,3Z",
    "link-variant": "M10.59,13.41C11,13.8 11,14.44 10.59,14.83C10.2,15.22 9.56,15.22 9.17,14.83C7.22,12.88 7.22,9.71 9.17,7.76V7.76L12.71,4.22C14.66,2.27 17.83,2.27 19.78,4.22C21.73,6.17 21.73,9.34 19.78,11.29L18.29,12.78C18.3,11.96 18.17,11.14 17.89,10.36L18.36,9.88C19.54,8.71 19.54,6.81 18.36,5.64C17.19,4.46 15.29,4.46 14.12,5.64L10.59,9.17C9.41,10.34 9.41,12.24 10.59,13.41M13.41,9.17C13.8,8.78 14.44,8.78 14.83,9.17C16.78,11.12 16.78,14.29 14.83,16.24V16.24L11.29,19.78C9.34,21.73 6.17,21.73 4.22,19.78C2.27,17.83 2.27,14.66 4.22,12.71L5.71,11.22C5.7,12.04 5.83,12.86 6.11,13.65L5.64,14.12C4.46,15.29 4.46,17.19 5.64,18.36C6.81,19.54 8.71,19.54 9.88,18.36L13.41,14.83C14.59,13.66 14.59,11.76 13.41,10.59C13,10.2 13,9.56 13.41,9.17Z",
    "play-circle-outline": "M12,20C7.59,20 4,16.41 4,12C4,7.59 7.59,4 12,4C16.41,4 20,7.59 20,12C20,16.41 16.41,20 12,20M12,2A10,10 0 0,0 2,12A10,10 0 0,0 12,22A10,10 0 0,0 22,12A10,10 0 0,0 12,2M10,16.5L16,12L10,7.5V16.5Z",
    "calendar-account": "M12 9C14 9 15 11.42 13.59 12.84C12.17 14.26 9.75 13.25 9.75 11.25C9.75 10 10.75 9 12 9M16.5 18H7.5V16.88C7.5 15.63 9.5 14.63 12 14.63S16.5 15.63 16.5 16.88M19 19H5V8H19M16 1V3H8V1H6V3H5C3.9 3 3 3.9 3 5V19C3 20.11 3.9 21 5 21H19C20.11 21 21 20.11 21 19V5C21 3.9 20.11 3 19 3H18V1H16Z",
    "bell-outline": "M10 21H14C14 22.1 13.1 23 12 23S10 22.1 10 21M21 19V20H3V19L5 17V11C5 7.9 7 5.2 10 4.3V4C10 2.9 10.9 2 12 2S14 2.9 14 4V4.3C17 5.2 19 7.9 19 11V17L21 19M17 11C17 8.2 14.8 6 12 6S7 8.2 7 11V18H17V11Z",
    "calendar-remove": "M19,19H5V8H19M19,3H18V1H16V3H8V1H6V3H5C3.89,3 3,3.9 3,5V19A2,2 0 0,0 5,21H19A2,2 0 0,0 21,19V5A2,2 0 0,0 19,3M9.31,17L11.75,14.56L14.19,17L15.25,15.94L12.81,13.5L15.25,11.06L14.19,10L11.75,12.44L9.31,10L8.25,11.06L10.69,13.5L8.25,15.94L9.31,17Z",
    "human-child": "M12,2A3,3 0 0,1 15,5A3,3 0 0,1 12,8A3,3 0 0,1 9,5A3,3 0 0,1 12,2M11,22H8V16H6V9H18V16H16V22H13V18H11V22Z",
    "trash-can-outline": "M9,3V4H4V6H5V19A2,2 0 0,0 7,21H17A2,2 0 0,0 19,19V6H20V4H15V3H9M7,6H17V19H7V6M9,8V17H11V8H9M13,8V17H15V8H13Z",
    "translate": "M12.87,15.07L10.33,12.56L10.36,12.53C12.1,10.59 13.34,8.36 14.07,6H17V4H10V2H8V4H1V6H12.17C11.5,7.92 10.44,9.75 9,11.35C8.07,10.32 7.3,9.19 6.69,8H4.69C5.42,9.63 6.42,11.17 7.67,12.56L2.58,17.58L4,19L9,14L12.11,17.11L12.87,15.07M18.5,10H16.5L12,22H14L15.12,19H19.87L21,22H23L18.5,10M15.88,17L17.5,12.67L19.12,17H15.88Z",
    "file-outline": "M14,2H6A2,2 0 0,0 4,4V20A2,2 0 0,0 6,22H18A2,2 0 0,0 20,20V8L14,2M18,20H6V4H13V9H18V20Z",
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
        "text": "The class visits the natural history museum on Friday.\nPlease bring a packed lunch and sign the permission slip.",
        "type": "info",
        "author": "Ms Brown",
        "achievement": "sign",
        "achieved": False,
        "medias": [
            {"id": "m1", "name": "Map.png", "extension": "png"},
            {"id": "m2", "name": "Permission slip.pdf", "extension": "pdf"},
        ],
        "date": "2026-11-16T07:30:00+01:00",
        "children": ["p1"],
        "child": "Alex",
        "to_sign": True,
        "to_do": True,
    },
    {
        "id": "102",
        "title": "Swimming lessons start",
        "text": "Lessons start on Monday 30 November. A swim cap is required.",
        "type": "alert",
        "author": "Mr Green",
        "achievement": "read",
        "achieved": False,
        "medias": [],
        "date": "2026-11-12T16:00:00+01:00",
        "children": ["p2"],
        "child": "Sam",
        "to_sign": False,
        "to_do": True,
    },
    {
        "id": "103",
        "title": "Christmas lunch",
        "text": "The canteen serves a Christmas lunch on Thursday 17 December.",
        "type": "info",
        "author": "Ms Brown",
        "achievement": "survey",
        "achieved": False,
        "medias": [],
        "date": "2026-11-11T12:00:00+01:00",
        "children": ["p1"],
        "child": "Alex",
        "to_sign": False,
        "to_do": True,
        "commentable": True,
        "comments": 2,
        "survey": {
            "deadline": "2026-12-04",
            "anonymous": False,
            "one_per_child": True,
            "questions": [
                {
                    "id": "1",
                    "label": "Will Alex eat at the canteen that day?",
                    "multiple": False,
                    "options": [{"id": "a", "label": "Yes"}, {"id": "b", "label": "No"}],
                },
                {
                    "id": "2",
                    "label": "Can you help with the decorations?",
                    "multiple": True,
                    "options": [
                        {"id": "m", "label": "Monday"},
                        {"id": "t", "label": "Tuesday"},
                        {"id": "w", "label": "Wednesday"},
                    ],
                },
            ],
            "answers": {},
        },
        "slots": [],
    },
]

# The conversation of the Christmas lunch message, as the comments websocket answers it.
COMMENTS = [
    {
        "id": "c1",
        "author": "Ms Brown",
        "mine": False,
        "text": "Hello, can you tell me if Alex has a food allergy?",
        "date": "2026-11-12T08:10:00+01:00",
        "deleted": False,
        "medias": [],
    },
    {
        "id": "c2",
        "author": "Parent",
        "mine": True,
        "text": "No allergy, thank you for asking.",
        "date": "2026-11-12T19:30:00+01:00",
        "deleted": False,
        "medias": [],
    },
]


def _hw(id_, title, subject, due, done, *, text="", achievement="check"):
    return {
        "id": id_,
        "title": title,
        "text": text,
        "subject": subject,
        "due": due,
        "done": done,
        "achievement": achievement,
        "achieved": done,
        "recipient_id": f"r-{id_}" if achievement == "check" else "",
        "medias": [],
        "type": "lesson",
        "author": "",
    }


HOMEWORK = {
    "p1": [
        _hw(
            "h1", "Learn the poem, page 12", "French", "2026-11-19", False, text="Learn the first two verses by heart."
        ),
        _hw("h2", "Times table of 7", "Maths", "2026-11-19", False),
        _hw("h3", "Read chapter 3", "French", "2026-11-16", True, achievement="read"),
    ],
    "p2": [
        _hw("h4", "Bring a cardboard box", "Art", "2026-11-20", False),
    ],
}


def _news(id_, title, type_, date, author, text=""):
    return {
        "id": id_,
        "title": title,
        "text": text,
        "type": type_,
        "author": author,
        "achievement": "",
        "achieved": False,
        "medias": [],
        "date": date,
        "children": [],
        "child": "",
        "to_sign": False,
        "to_do": False,
    }


NEWS = [
    _news("n1", "Christmas fair", "event", "2026-11-15T10:00:00+01:00", "Head teacher", "Saturday 12 December, 10:00."),
    {
        **_news(
            "n2", "Parents' evening", "meeting", "2026-11-13T18:00:00+01:00", "Ms Brown", "Book a slot to meet me."
        ),
        "achievement": "book",
        "children": ["p1", "p2"],
        "child": "Alex · Sam",
        "to_do": True,
        "slots": [
            {
                "id": "s1",
                "start": "2026-11-24T17:00:00+01:00",
                "end": "2026-11-24T17:15:00+01:00",
                "location": "Room 4",
                "booked": True,
                "child_id": "p1",
            },
            *[
                {
                    "id": f"s{i}",
                    "start": f"2026-11-24T{17 + (i * 15) // 60}:{(i * 15) % 60:02d}:00+01:00",
                    "end": f"2026-11-24T{17 + ((i + 1) * 15) // 60}:{((i + 1) * 15) % 60:02d}:00+01:00",
                    "location": "Room 4",
                    "booked": False,
                    "child_id": "",
                }
                for i in range(2, 7)
            ],
        ],
    },
    _news("n3", "Canteen menus for December", "advert", "2026-11-10T09:00:00+01:00", "Town hall"),
]


DOCUMENTS = [
    {
        "id": "notebook:21",
        "kind": "notebook",
        "title": "School report",
        "type": "Term 1",
        "year": "2026-2027",
        "date": "2026-11-13T00:00:00+01:00",
        "child_id": "p1",
        "child": "Alex",
        "signed": False,
        "to_sign": True,
        "file": True,
    },
    {
        "id": "attestation:7",
        "kind": "attestation",
        "title": "Swimming test",
        "type": "",
        "year": "2026",
        "date": "2026-06-30T00:00:00+02:00",
        "child_id": "p1",
        "child": "Alex",
        "signed": True,
        "to_sign": False,
        "file": True,
    },
    {
        "id": "notebook:20",
        "kind": "notebook",
        "title": "School report",
        "type": "Term 3",
        "year": "2025-2026",
        "date": "2026-07-03T00:00:00+02:00",
        "child_id": "p2",
        "child": "Sam",
        "signed": True,
        "to_sign": False,
        "file": True,
    },
]


ACTIVITIES = [
    {
        "id": "a1",
        "title": "Pumpkin soup workshop",
        "text": "This morning we cooked a pumpkin soup and tasted it together.",
        "type": "activity",
        "author": "Ms Brown",
        "achievement": "",
        "achieved": False,
        "medias": [{"id": "m31", "name": "soup.jpg", "extension": "jpg"}],
        "links": [{"url": "https://example.org/pumpkin-song", "title": "The pumpkin song", "type": "video"}],
        "archived": False,
        "date": "2026-11-20T10:00:00+01:00",
        "children": ["p1"],
        "child": "Alex",
        "likes": 6,
        "like_id": "12",
        "commentable": True,
        "comments": 0,
    },
    {
        "id": "a2",
        "title": "Autumn walk in the park",
        "text": "We picked leaves for the class herbarium.",
        "type": "activity",
        "author": "Mr Green",
        "achievement": "",
        "achieved": False,
        "medias": [],
        "links": [],
        "archived": False,
        "date": "2026-11-17T15:00:00+01:00",
        "children": ["p2"],
        "child": "Sam",
        "likes": 3,
        "like_id": "",
        "commentable": False,
        "comments": 0,
    },
]

NOTIFICATIONS = [
    {
        "id": "901",
        "type": "message-event_canceled",
        "subject": "message",
        "subject_id": "n2",
        "text": "",
        "author": "Ms Brown",
        "start": "2026-11-24T17:30:00+01:00",
        "end": "2026-11-24T17:45:00+01:00",
        "date": "2026-11-12T09:00:00+01:00",
    },
    {
        "id": "902",
        "type": "activity",
        "subject": "activity",
        "subject_id": "a1",
        "text": "New post in the class life: Pumpkin soup workshop",
        "author": "",
        "start": None,
        "end": None,
        "date": "2026-11-11T10:05:00+01:00",
    },
]

APPOINTMENTS = [
    {
        "id": "s1",
        "start": "2026-11-24T17:00:00+01:00",
        "end": "2026-11-24T17:15:00+01:00",
        "location": "Room 4",
        "child_id": "p1",
        "child": "Alex",
        "message_id": "n2",
        "title": "Parents' evening",
    }
]


# The map attached to the trip message: a neutral drawing, served as the signed URL of the file view.
MOCK_IMAGE = "data:image/svg+xml," + quote(
    '<svg xmlns="http://www.w3.org/2000/svg" width="240" height="140"><rect width="240" height="140" fill="#e8efe3"/>'
    '<path d="M0 100 Q60 80 120 105 T240 95 V140 H0Z" fill="#b9d4ea"/><path d="M40 0 L60 140 M150 0 L140 140" '
    'stroke="#fff" stroke-width="6"/><rect x="160" y="40" width="40" height="22" rx="3" fill="#d8c29a"/>'
    '<circle cx="180" cy="51" r="4" fill="#f28c1e"/></svg>'
)


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
        _sensor("sensor.educartable_school_reports_to_sign", 1, stale=[], documents=DOCUMENTS),
        _sensor("sensor.educartable_class_life", 2, stale=[], activities=ACTIVITIES),
        _sensor("sensor.educartable_unread_notifications", 2, stale=[], notifications=NOTIFICATIONS),
        _sensor(
            "sensor.educartable_next_appointment", "2026-11-24T16:00:00+00:00", stale=[], appointments=APPOINTMENTS
        ),
        *[_homework_sensor(ch, HOMEWORK[ch["id"]]) for ch in CHILDREN],
        _sensor(
            "sensor.educartable_last_update",
            "2026-11-16T07:58:00+00:00",
            stale=[],
            account={"name": "Parent"},
            children=CHILDREN,
            panel_tabs=["homework", "words", "news", "activities", "documents"],
            hide_header="off",
        ),
    ]
}

# Everything signed: the header picture shows the homework left (the pen writes).
STATES_SIGNED = {
    **STATES,
    "sensor.educartable_liaison_book_to_sign": _sensor(
        "sensor.educartable_liaison_book_to_sign",
        0,
        stale=[],
        messages=[{**m, "achieved": True, "to_sign": False, "to_do": False} for m in CARNET],
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
    # The confirmation at the top of the card before signing a liaison-book message, the signer's name prefilled.
    {"file": "card-sign", "theme": "light", "config": {}, "click": '[data-action="sign"]'},
    {"file": "card-sign-dark", "theme": "dark", "config": {}, "click": '[data-action="sign"]'},
    # A message unfolded to its text and attachments, by a click on its row.
    {"file": "card-unfolded", "theme": "light", "config": {}, "click": '[data-toggle="word:101"]'},
    {"file": "card-unfolded-dark", "theme": "dark", "config": {}, "click": '[data-toggle="word:101"]'},
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
    {"file": "panel-activities", "theme": "light", "panel": "activities", "width": 960},
    {"file": "panel-activities-dark", "theme": "dark", "panel": "activities", "width": 960},
    {"file": "panel-documents", "theme": "light", "panel": "documents", "width": 960},
    {"file": "panel-documents-dark", "theme": "dark", "panel": "documents", "width": 960},
    # The conversation of a message with the teacher, opened under it (its survey above).
    {"file": "panel-conversation", "theme": "light", "panel": "words", "width": 960, "click": '[data-action="thread"]'},
    {
        "file": "panel-conversation-dark",
        "theme": "dark",
        "panel": "words",
        "width": 960,
        "click": '[data-action="thread"]',
    },
    # A new message to the teacher, from the Liaison book.
    {"file": "panel-write", "theme": "light", "panel": "words", "width": 960, "click": '[data-action="write"]'},
    {"file": "panel-write-dark", "theme": "dark", "panel": "words", "width": 960, "click": '[data-action="write"]'},
    # The sidebar entry with its badge: 1 message to sign + 3 homework + 1 school report = 5, like the mock sensors.
    {"file": "sidebar", "theme": "light", "sidebar": True, "count": 5, "width": 256},
    {"file": "sidebar-dark", "theme": "dark", "sidebar": True, "count": 5, "width": 256},
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
        """({config, states, element, tab, dark, mockImage, comments}) => {
          const hass = {states, themes: {darkMode: dark}, language: "en", locale: {language: "en", time_format: "24"}, user: {is_admin: true},
                        callService: () => Promise.resolve(),
                        callWS: (msg) => Promise.resolve(msg.type === "auth/sign_path" ? {path: mockImage} : msg.type === "educartable/comments" ? {comments} : {})};
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
            "mockImage": MOCK_IMAGE,
            "comments": COMMENTS,
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
