# Pinned uv version copied onto a plain, precisely-tagged Python base. More
# precise than using astral's combined uv+python image directly, since that
# tag can move; this way both the Python version and the uv version are each
# pinned independently.
FROM python:3.13-slim-bookworm

COPY --from=ghcr.io/astral-sh/uv:0.12.5 /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

# Install dependencies first, separately from app code, so Docker can cache
# this layer and skip reinstalling everything when only source files change.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project

COPY src/ ./src/
COPY README.md ./
RUN uv sync --frozen

# Run as a dedicated non-root user rather than the default root. Limits
# blast radius if the app or a dependency is ever compromised.
RUN groupadd --system app && useradd --system --gid app --no-create-home app \
    && chown -R app:app /app
USER app

EXPOSE 8000

# Call the venv's uvicorn directly rather than "uv run", which needs a
# writable cache dir under $HOME. The app user has none (--no-create-home
# above), and dependencies are already fully installed by this point anyway.
CMD [".venv/bin/uvicorn", "homepage_exposure_status.api:app", "--host", "0.0.0.0", "--port", "8000"]
