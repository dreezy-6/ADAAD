# SPDX-License-Identifier: MIT
"""Deploy Manifest Generator — ADAAD Phase 10, M10-03.

Generates one-click deployment manifests for the major cloud platforms,
lowering the barrier to a running ADAAD instance to near-zero.

Supported platforms:
  - Railway (railway.json)
  - Render   (render.yaml)
  - Docker   (Dockerfile + docker-compose.yml)
  - Fly.io   (fly.toml)

All manifests are parametrised — org_id, tier, Stripe keys, etc. are
injected via environment variables so secrets never appear in generated files.

Author: Dustin L. Reid · InnovativeAI LLC
"""

from __future__ import annotations

import json
import textwrap
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional


class DeployPlatform(str, Enum):
    RAILWAY      = "railway"
    RENDER       = "render"
    DOCKER       = "docker"
    FLY          = "fly"


@dataclass
class DeployConfig:
    """Parameters for a deployment manifest."""
    platform: DeployPlatform
    service_name: str    = "adaad"
    python_version: str  = "3.11.9"
    port: int            = 8000
    region: str          = "us-central"
    memory_mb: int       = 512
    cpu: float           = 0.5
    include_redis: bool  = False
    include_postgres: bool = False
    custom_env: Dict[str, str] = None   # type: ignore

    def __post_init__(self) -> None:
        if self.custom_env is None:
            self.custom_env = {}


# ---------------------------------------------------------------------------
# Required env vars (shown in all manifests as placeholders)
# ---------------------------------------------------------------------------

_REQUIRED_ENV = {
    "ADAAD_CLAUDE_API_KEY":    "your-anthropic-api-key",
    "ADAAD_ADMIN_TOKEN":       "your-admin-token-min-32-chars",
    "ADAAD_ENV":               "production",
    "ADAAD_HMAC_SECRET":       "your-hmac-secret-min-32-chars",
    "STRIPE_SECRET_KEY":       "sk_live_...",
    "STRIPE_WEBHOOK_SECRET":   "whsec_...",
    "STRIPE_PRO_PRICE_ID":     "price_...",
    "STRIPE_ENTERPRISE_PRICE_ID": "price_...",
    "ADAAD_REFERRAL_SECRET":   "your-referral-hmac-secret",
    "GITHUB_WEBHOOK_SECRET":   "your-github-webhook-secret",
}


def _env_block_yaml(indent: int = 4) -> str:
    pad = " " * indent
    lines = []
    for k, v in _REQUIRED_ENV.items():
        lines.append(f"{pad}- key: {k}")
        lines.append(f"{pad}  value: {v}   # REPLACE")
    return "\n".join(lines)


def _env_block_toml() -> str:
    lines = []
    for k, v in _REQUIRED_ENV.items():
        lines.append(f'  {k} = "{v}"  # REPLACE')
    return "\n".join(lines)


def _env_block_docker_compose() -> str:
    lines = []
    for k, v in _REQUIRED_ENV.items():
        lines.append(f"      - {k}={v}  # REPLACE")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Railway manifest
# ---------------------------------------------------------------------------

def generate_railway_json(cfg: DeployConfig) -> str:
    """Generate railway.json for one-click Railway deploy."""
    manifest: Dict[str, Any] = {
        "$schema": "https://railway.app/railway.schema.json",
        "build": {
            "builder": "NIXPACKS",
            "buildCommand": "pip install -r requirements.server.txt"
        },
        "deploy": {
            "startCommand": f"uvicorn server:app --host 0.0.0.0 --port {cfg.port}",
            "healthcheckPath": "/health",
            "healthcheckTimeout": 30,
            "restartPolicyType": "ON_FAILURE",
            "restartPolicyMaxRetries": 5,
        },
    }
    return json.dumps(manifest, indent=2)


def generate_railway_readme_section() -> str:
    """Markdown deploy-to-Railway button + instructions."""
    return textwrap.dedent("""\
        ## Deploy to Railway

        [![Deploy on Railway](https://railway.app/button.svg)](https://railway.app/template/ADAAD?referralCode=innovativeai)

        1. Click the button above
        2. Set the required environment variables (see table below)
        3. Railway will auto-deploy from this repo — your ADAAD instance is live in ~2 minutes

        | Variable | Description |
        |---|---|
        | `ADAAD_CLAUDE_API_KEY` | Anthropic API key for mutation agents |
        | `ADAAD_ADMIN_TOKEN` | Secret token for `/api/admin/*` routes |
        | `STRIPE_SECRET_KEY` | Stripe secret key for billing |
        | `STRIPE_WEBHOOK_SECRET` | Stripe webhook signing secret |
        | `ADAAD_HMAC_SECRET` | HMAC secret for API key signing |
        | `GITHUB_WEBHOOK_SECRET` | GitHub App webhook secret |
    """)


# ---------------------------------------------------------------------------
# Render manifest
# ---------------------------------------------------------------------------

def generate_render_yaml(cfg: DeployConfig) -> str:
    """Generate render.yaml for one-click Render deploy."""
    services_block = textwrap.dedent(f"""\
        services:
          - type: web
            name: {cfg.service_name}
            runtime: python
            region: {cfg.region}
            plan: starter
            buildCommand: pip install -r requirements.server.txt
            startCommand: uvicorn server:app --host 0.0.0.0 --port {cfg.port}
            healthCheckPath: /health
            envVars:
    """)
    services_block += _env_block_yaml(indent=6)

    if cfg.include_redis:
        services_block += textwrap.dedent(f"""
          - type: redis
            name: {cfg.service_name}-redis
            region: {cfg.region}
            plan: starter
            maxmemoryPolicy: allkeys-lru
        """)

    if cfg.include_postgres:
        services_block += textwrap.dedent(f"""
          - type: pserv
            name: {cfg.service_name}-postgres
            region: {cfg.region}
            plan: starter
            databaseName: adaad
            databaseUser: adaad
        """)

    return services_block


# ---------------------------------------------------------------------------
# Dockerfile
# ---------------------------------------------------------------------------

def generate_dockerfile(cfg: DeployConfig) -> str:
    """Generate a production-grade multi-stage Dockerfile."""
    return textwrap.dedent(f"""\
        # syntax=docker/dockerfile:1
        # ADAAD — Production Dockerfile
        # Build: docker build -t adaad .
        # Run:   docker run -p {cfg.port}:{cfg.port} --env-file .env adaad

        # ── Stage 1: builder ──────────────────────────────────────────
        FROM python:{cfg.python_version}-slim AS builder

        WORKDIR /app

        # Install build deps
        RUN apt-get update && apt-get install -y --no-install-recommends \\
            gcc git && \\
            rm -rf /var/lib/apt/lists/*

        COPY requirements.server.txt .
        RUN pip install --no-cache-dir --prefix=/install -r requirements.server.txt

        # ── Stage 2: runtime ──────────────────────────────────────────
        FROM python:{cfg.python_version}-slim AS runtime

        WORKDIR /app

        # Copy installed packages from builder
        COPY --from=builder /install /usr/local

        # Copy application source
        COPY . .

        # Non-root user for security
        RUN useradd -m -u 1001 adaad && chown -R adaad:adaad /app
        USER adaad

        # Health check
        HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \\
            CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:{cfg.port}/health')" || exit 1

        EXPOSE {cfg.port}

        ENV PYTHONUNBUFFERED=1 \\
            PYTHONDONTWRITEBYTECODE=1 \\
            PORT={cfg.port}

        CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "{cfg.port}", "--workers", "2"]
    """)


def generate_docker_compose(cfg: DeployConfig) -> str:
    """Generate docker-compose.yml for local + self-hosted deployment."""
    redis_service = ""
    redis_depends = ""
    redis_env = ""
    if cfg.include_redis:
        redis_service = textwrap.dedent("""\
          redis:
            image: redis:7-alpine
            restart: unless-stopped
            command: redis-server --maxmemory 128mb --maxmemory-policy allkeys-lru
            healthcheck:
              test: ["CMD", "redis-cli", "ping"]
              interval: 10s
              timeout: 5s
              retries: 5
        """)
        redis_depends = "\n      - redis"
        redis_env = "\n      - REDIS_URL=redis://redis:6379/0"

    svc = cfg.service_name
    return textwrap.dedent(f"""\
        version: "3.9"

        services:
          {svc}:
            build: .
            image: innovativeai/{svc}:latest
            restart: unless-stopped
            ports:
              - "{cfg.port}:{cfg.port}"
            environment:
{_env_block_docker_compose()}{redis_env}
            healthcheck:
              test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:{cfg.port}/health')"]
              interval: 30s
              timeout: 10s
              start_period: 20s
              retries: 3
            depends_on:{redis_depends}
              []
        {redis_service}
        volumes:
          adaad_data:
    """)


# ---------------------------------------------------------------------------
# Fly.io manifest
# ---------------------------------------------------------------------------

def generate_fly_toml(cfg: DeployConfig) -> str:
    """Generate fly.toml for Fly.io deployment."""
    return textwrap.dedent(f"""\
        # fly.toml — ADAAD on Fly.io
        # Deploy: fly launch --copy-config --no-deploy && fly secrets set ADAAD_CLAUDE_API_KEY=... && fly deploy

        app = "{cfg.service_name}"
        primary_region = "iad"    # Washington D.C. — change as needed

        [build]
          dockerfile = "Dockerfile"

        [env]
{_env_block_toml()}

        [http_service]
          internal_port   = {cfg.port}
          force_https     = true
          auto_stop_machines  = true
          auto_start_machines = true
          min_machines_running = 1
          processes = ["app"]

        [[vm]]
          memory = "{cfg.memory_mb}mb"
          cpu_kind = "shared"
          cpus = 1

        [checks]
          [checks.health]
            grace_period = "15s"
            interval     = "30s"
            method       = "GET"
            path         = "/health"
            port         = {cfg.port}
            timeout      = "10s"
            type         = "http"
    """)


# ---------------------------------------------------------------------------
# Bundle generator — produce all manifests at once
# ---------------------------------------------------------------------------

@dataclass
class DeployBundle:
    railway_json: str
    render_yaml: str
    dockerfile: str
    docker_compose_yaml: str
    fly_toml: str
    railway_readme_section: str

    def files(self) -> Dict[str, str]:
        return {
            "railway.json":         self.railway_json,
            "render.yaml":          self.render_yaml,
            "Dockerfile":           self.dockerfile,
            "docker-compose.yml":   self.docker_compose_yaml,
            "fly.toml":             self.fly_toml,
        }


def generate_all(cfg: Optional[DeployConfig] = None) -> DeployBundle:
    """Generate the full deployment bundle from a single config."""
    if cfg is None:
        cfg = DeployConfig(platform=DeployPlatform.DOCKER)
    return DeployBundle(
        railway_json=generate_railway_json(cfg),
        render_yaml=generate_render_yaml(cfg),
        dockerfile=generate_dockerfile(cfg),
        docker_compose_yaml=generate_docker_compose(cfg),
        fly_toml=generate_fly_toml(cfg),
        railway_readme_section=generate_railway_readme_section(),
    )
