"""Entry point for running the API.

Use this instead of calling `uvicorn app.main:app` directly.

Uvicorn's `proxy_headers` option defaults to **True**, which makes it rewrite
`request.client` from the X-Forwarded-For header before any application code
runs. With no proxy in front, any client can send that header and so hand
itself a new identity on every request, which defeats per-IP rate limiting
entirely. The application's `trust_proxy_headers` setting cannot prevent this
on its own, because the rewrite has already happened by the time a request
reaches it.

This module ties the two together: uvicorn only honours forwarded headers when
the application is configured to trust them.

    python run.py                      # development, with reload
    python run.py --host 0.0.0.0       # bind publicly
"""

from __future__ import annotations

import argparse
import logging
import os

import uvicorn

from app.config import get_settings

logger = logging.getLogger(__name__)


def main() -> None:
    settings = get_settings()

    # Hosts assign the port through the environment, and a container must bind
    # 0.0.0.0 or nothing outside it can connect. Defaults stay local-only so
    # running this on a laptop does not expose the API to the network.
    parser = argparse.ArgumentParser(description="Run the ProjectRevive API.")
    parser.add_argument("--host", default=os.environ.get("HOST", "127.0.0.1"))
    parser.add_argument(
        "--port", type=int, default=int(os.environ.get("PORT", "8000"))
    )
    parser.add_argument(
        "--reload",
        action=argparse.BooleanOptionalAction,
        default=os.environ.get("RELOAD", "true").lower() == "true",
        help="Reload on code changes. Turn off in production.",
    )
    args = parser.parse_args()

    trust = settings.trust_proxy_headers
    if trust:
        logger.warning(
            "Forwarded headers are TRUSTED. Only correct behind a proxy that "
            "overwrites X-Forwarded-For; otherwise clients can spoof their "
            "address and bypass per-IP rate limits."
        )

    uvicorn.run(
        "app.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        # The whole point of this file.
        proxy_headers=trust,
        forwarded_allow_ips=settings.forwarded_allow_ips if trust else None,
    )


if __name__ == "__main__":
    main()
