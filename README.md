# MSDSO-Analyst
r/MSDSO community Discord bot.

## Features
- **Role panel**: a message in #roles with one button per role group (General, Cohort, Classes). Clicking one opens a
  private dropdown showing the member's current roles in that group; submitting it adds and removes roles to match.
- **FAQ publishing**: the pinned FAQ messages live as Markdown files in [`faq/`](faq) and are pushed to Discord with
  `/faq publish`.
- **Moderator slash commands** (owner, Administrator, or Moderator role only): `/roles ...`, `/faq publish`,
  `/status`, `/purge`, `/assign`, `/edit`, `/react_to_message`, `/echo`, `/shutdown`.

## Setup
Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/).

```sh
uv sync
cp .env.example .env   # then set DISCORD_TOKEN
uv run msdso-analyst
```

In the Discord developer portal, the bot needs the **Server Members** privileged intent. In the server it needs the
Manage Roles, Send Messages, Manage Messages, and Read Message History permissions, and its role must sit above any
role it hands out.

## Docker
Every push to `main` publishes `ghcr.io/msdso/msdso-analyst:latest` (plus a `sha-<commit>` tag). Pushing a `v*` tag
also publishes version tags, e.g. `v2.0.0` → `2.0.0` and `2.0`. Pull requests build the image without publishing it.

To run on a server, put `DISCORD_TOKEN=...` in a `.env` next to [`compose.yaml`](compose.yaml), then:

```sh
docker compose pull && docker compose up -d
```

`config/server.toml` and `faq/` are baked into the image. To change the config without rebuilding, mount your own
copy: `-v ./server.toml:/app/config/server.toml:ro`. The bot's database lives in the `bot-data` volume at
`/app/data`; back it up with
`docker compose cp bot:/app/data/msdso.db ./msdso.db`.

## Configuration
[`config/server.toml`](config/server.toml) holds the guild ID, the moderator roles, and the role groups to start the
role panel with. Set `MSDSO_CONFIG` to use a different config file (e.g. for a test server).

Everything the bot changes at runtime lives in a SQLite database at `data/msdso.db` (`MSDSO_DB` to move it). On first
start the role groups are copied from `server.toml`; after that the database is the source of truth, and editing the
`[[role_groups]]` section has no effect.

## Role panel
Moderators manage it with `/roles`:

| Command | What it does |
| --- | --- |
| `/roles post channel:#roles` | Post the panel, deleting the previous one |
| `/roles create group:Cohort name:Fall 2026 Cohort emoji:🔟` | Create a new role (no permissions) and make it pickable |
| `/roles add group:Cohort role:@Fall 2026 Cohort emoji:🔟` | Make an existing role pickable (moves it if it's in another group) |
| `/roles remove role:@...` | Stop offering a role; members who have it keep it |
| `/roles new-group name:... max_choices:1 description:...` | Add a group (a button). `max_choices` 0 = any number |
| `/roles delete-group group:...` | Remove a group; members keep their roles |
| `/roles list` | Show every group and its roles |

The posted panel updates itself when groups or roles change. The bot refuses to offer `@everyone`, integration roles,
roles with moderator permissions, and roles above its own. A group holds at most 25 roles (Discord's dropdown limit).

## FAQ
Each file in [`faq/`](faq) is one Discord message: TOML front matter, then the message content (Discord markdown, up to
2,000 characters).

```markdown
+++
channel_id = 851535255080271951
message_id = 855846351433629697  # optional: existing bot message to edit
+++
**__Program Information__**
...
```

To change the FAQ, edit the file, merge to `main`, deploy the new image, then run `/faq publish` (or
`/faq publish name:program-information` for one file). The bot edits each file's message in place and skips ones that
are already up to date. A file with no `message_id`, or whose message was deleted, is posted as a new message, and the
bot remembers it for next time. It only edits its own messages.

## Development
```sh
uv run pytest
uv run ruff check . && uv run ruff format .
```
