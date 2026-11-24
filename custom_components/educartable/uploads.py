"""Files attached to a reply or a new message: uploaded from the panel, or read from a path Home Assistant may read.

The panel cannot reach the portal: it sends each file to Home Assistant first (an administrator's upload, kept a few
minutes in memory under a random token), then names the tokens in the reply or new message action. An automation
names files instead (a camera snapshot, a document), read only from the directories Home Assistant is allowed to read
(`allowlist_external_dirs`).
"""

from __future__ import annotations

import mimetypes
import os
import secrets
import time
from dataclasses import dataclass

from homeassistant.core import HomeAssistant

from .api import EducartableError

# What the portal accepts (its own uploader's limit and kinds of files).
MAX_FILE_BYTES = 40 * 1024 * 1024
MAX_FILES = 10
UPLOAD_TTL = 15 * 60
ALLOWED_EXTENSIONS = frozenset(
    {
        "jpg", "jpeg", "png", "gif", "heic", "webp",
        "pdf", "txt", "rtf", "doc", "docx", "xls", "xlsx", "ppt", "pptx", "odt", "ods", "odp",
        "mp3", "m4a", "wav", "ogg", "wma",
        "mp4", "mov", "avi", "webm", "mpeg",
    }
)  # fmt: skip
TOKEN_PREFIX = "upload:"


@dataclass(frozen=True)
class Attachment:
    name: str
    body: bytes
    content_type: str


def check_file(name: str, size: int) -> str:
    """The file's clean name, or an error when the portal would refuse it."""
    clean = os.path.basename(name.replace("\\", "/")).strip() or "file"
    ext = clean.rsplit(".", 1)[-1].lower() if "." in clean else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise EducartableError(f"{clean}: this kind of file is not accepted")
    if size > MAX_FILE_BYTES:
        raise EducartableError(f"{clean} is larger than 40 MB")
    return clean


def content_type(name: str) -> str:
    return mimetypes.guess_type(name)[0] or "application/octet-stream"


class UploadStore:
    """Files uploaded from the panel, by token, until they are sent or a few minutes pass."""

    def __init__(self) -> None:
        self._files: dict[str, tuple[float, str, Attachment]] = {}

    def _purge(self) -> None:
        now = time.monotonic()
        for token in [t for t, (at, _, _) in self._files.items() if now - at > UPLOAD_TTL]:
            del self._files[token]

    def add(self, user_id: str, name: str, body: bytes) -> str:
        self._purge()
        clean = check_file(name, len(body))
        token = TOKEN_PREFIX + secrets.token_urlsafe(18)
        self._files[token] = (time.monotonic(), user_id, Attachment(clean, body, content_type(clean)))
        return token

    def take(self, token: str) -> Attachment:
        self._purge()
        entry = self._files.pop(token, None)
        if entry is None:
            raise EducartableError("an attached file expired, add it again")
        return entry[2]


async def resolve(hass: HomeAssistant, store: UploadStore, refs: list[str]) -> list[Attachment]:
    """The files named by an action: upload tokens, or paths Home Assistant is allowed to read."""
    if len(refs) > MAX_FILES:
        raise EducartableError(f"{MAX_FILES} files at most")
    out = []
    for ref in refs:
        if ref.startswith(TOKEN_PREFIX):
            out.append(store.take(ref))
            continue
        path = os.path.realpath(ref)
        if not hass.config.is_allowed_path(path) or not os.path.isfile(path):
            raise EducartableError(f"{os.path.basename(ref)}: not a file Home Assistant may read")
        clean = check_file(path, os.path.getsize(path))
        body = await hass.async_add_executor_job(_read, path)
        out.append(Attachment(clean, body, content_type(clean)))
    return out


def _read(path: str) -> bytes:
    with open(path, "rb") as file:
        return file.read(MAX_FILE_BYTES + 1)
