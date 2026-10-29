# MSDSO-Analyst
r/MSDSO community Discord bot.

## Features
- **Reaction roles**: reacting to the role, cohort, and class-access messages in #roles grants the matching role; removing the reaction removes it.
- **Moderator slash commands** (owner, Administrator, or Moderator role only): `/status`, `/purge`, `/assign`, `/edit`, `/react_to_message`, `/echo`, `/shutdown`.

## Setup
Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/).

```sh
uv sync
cp .env.example .env   # then set DISCORD_TOKEN
uv run msdso-analyst
```

In the Discord developer portal, the bot needs the **Server Members** privileged intent. In the server it needs the
Manage Roles, Manage Messages, Read Message History, and Add Reactions permissions, and its role must sit above any
role it hands out.

## Configuration
Server IDs (guild, moderator roles, reaction-role messages, emoji → role mapping) live in
[`config/server.toml`](config/server.toml). To add a new cohort or course:

1. Create the role in Discord and copy its ID.
2. Use `/react_to_message` to add the emoji to the right message in #roles.
3. Add `"<emoji>" = <role id>` under `[reaction_roles]` and restart the bot.

Set `MSDSO_CONFIG` to use a different config file (e.g. for a test server).

## Development
```sh
uv run pytest
uv run ruff check . && uv run ruff format .
```

`Discord FAQ/` holds the text of the pinned FAQ messages, posted with `/edit`.
