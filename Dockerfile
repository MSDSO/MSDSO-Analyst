# syntax=docker/dockerfile:1

FROM python:3.13-slim AS builder
COPY --from=ghcr.io/astral-sh/uv:0.12.18 /uv /bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=0
WORKDIR /app

# Dependencies first so they're cached across source-only changes.
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-dev --no-install-project

COPY pyproject.toml uv.lock README.md LICENSE ./
COPY src ./src
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --no-editable


FROM python:3.13-slim
RUN useradd --system --uid 10001 --no-create-home bot
WORKDIR /app
COPY --from=builder /app/.venv /app/.venv
COPY config ./config
ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1
USER bot
# DISCORD_TOKEN must be provided at runtime. Mount a file over /app/config/server.toml
# (or set MSDSO_CONFIG) to use a different server config.
CMD ["msdso-analyst"]
