"""Entry point for ProxAI daemon mode (python -m proxai._run)."""

import os
import sys

import click
import uvicorn


@click.command()
@click.option("--host", default="127.0.0.1")
@click.option("--port", default=8090, type=int)
@click.option("--dashboard-port", default=8091, type=int)
def main(host, port, dashboard_port):
    dashboard_enabled = os.getenv("PROXAI_DASHBOARD_ENABLED", "true").lower() == "true"

    if dashboard_enabled:
        import threading
        from proxai.dashboard.routes import dashboard_app

        def run_dashboard():
            uvicorn.run(dashboard_app, host=host, port=dashboard_port, log_level="warning")

        t = threading.Thread(target=run_dashboard, daemon=True)
        t.start()

    from proxai.server import app
    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level=os.getenv("PROXAI_LOG_LEVEL", "info").lower(),
    )


if __name__ == "__main__":
    main()
