"""Loads FAQ messages from Markdown files.

Each file is one Discord message: TOML front matter between ``+++`` lines, then the message content.

    +++
    channel_id = 851535255080271951
    message_id = 855846351433629697  # optional: an existing bot message to edit instead of posting a new one
    +++
    **__Program Information__**
    ...
"""

import tomllib
from dataclasses import dataclass
from pathlib import Path

from msdso_analyst.config import ConfigError

DEFAULT_FAQ_DIR = Path("faq")
MAX_MESSAGE_LENGTH = 2000
FENCE = "+++"


@dataclass(frozen=True)
class FaqEntry:
    slug: str
    channel_id: int
    message_id: int | None
    content: str


def parse_faq(slug: str, text: str) -> FaqEntry:
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].strip() != FENCE:
        raise ConfigError(f"{slug}: must start with a {FENCE} front matter block")
    try:
        end = next(i for i, line in enumerate(lines[1:], 1) if line.strip() == FENCE)
    except StopIteration:
        raise ConfigError(f"{slug}: front matter is missing its closing {FENCE}") from None
    try:
        meta = tomllib.loads("".join(lines[1:end]))
        channel_id = int(meta["channel_id"])
    except (tomllib.TOMLDecodeError, KeyError, ValueError) as e:
        raise ConfigError(f"{slug}: bad front matter ({e})") from e

    content = "".join(lines[end + 1 :]).strip()
    if not content:
        raise ConfigError(f"{slug}: has no content")
    if len(content) > MAX_MESSAGE_LENGTH:
        raise ConfigError(f"{slug}: is {len(content)} characters; Discord's limit is {MAX_MESSAGE_LENGTH}")
    message_id = meta.get("message_id")
    return FaqEntry(slug, channel_id, int(message_id) if message_id else None, content)


def load_faq(directory: Path | str = DEFAULT_FAQ_DIR) -> dict[str, FaqEntry]:
    """All FAQ entries in ``directory``, keyed by file name without ``.md``."""
    paths = sorted(Path(directory).glob("*.md"))
    return {p.stem: parse_faq(p.stem, p.read_text(encoding="utf-8")) for p in paths}
