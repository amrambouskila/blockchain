FROM python:3.13-slim AS build

RUN pip install --no-cache-dir uv

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

FROM python:3.13-slim

# Pull the Debian updates that exist today. The remaining high findings in
# util-linux, ncurses, sqlite, systemd, acl, and perl have no fixed package yet.
RUN apt-get update \
    && apt-get upgrade -y \
    && rm -rf /var/lib/apt/lists/*

# The app runs from the virtualenv. The base image's pip vendors certifi, msgpack,
# and urllib3, and its bill of materials lists an old setuptools. Those copies are
# not used at runtime.
RUN rm -rf \
    /usr/local/lib/python3.13/site-packages/pip \
    /usr/local/lib/python3.13/site-packages/pip-*.dist-info \
    /usr/local/lib/python3.13/ensurepip \
    /usr/local/bin/pip \
    /usr/local/bin/pip3 \
    /usr/local/bin/pip3.13

WORKDIR /app

COPY --from=build /app/.venv /app/.venv
COPY bitcoin_wallet.py constants.py ./
COPY blockchain_dev/bitcoin_wallet_dev/src/btc_wallet ./blockchain_dev/bitcoin_wallet_dev/src/btc_wallet
COPY blockchain_dev/edu_node/src/edu_node ./blockchain_dev/edu_node/src/edu_node

ENV PYTHONPATH=/app:/app/blockchain_dev/bitcoin_wallet_dev/src:/app/blockchain_dev/edu_node/src
ENV PATH="/app/.venv/bin:${PATH}"
ENV EDU_CHAIN_DIR=/data/chain

RUN mkdir -p /data/chain

EXPOSE 8000

# local-dev container, not a public-facing service,
# so non-root is exempt per global CLAUDE.md section 9.
# nosemgrep: dockerfile.security.missing-user.missing-user
CMD ["uvicorn", "edu_node.node_api:app", "--host", "0.0.0.0", "--port", "8000"]
