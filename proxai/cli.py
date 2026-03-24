"""ProxAI CLI — start, stop, status, logs, stats."""

import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import click
from dotenv import load_dotenv

PID_FILE = Path.home() / ".proxai" / "proxai.pid"
LOG_FILE = Path.home() / ".proxai" / "proxai.log"


def load_env():
    """Load .env from current directory or home."""
    for path in [Path(".env"), Path.home() / ".proxai" / ".env"]:
        if path.exists():
            load_dotenv(path)
            return


@click.group()
def cli():
    """ProxAI — API key proxy for AI providers."""
    pass


@cli.command()
@click.option("--host", default=None, help="Host to bind (overrides PROXAI_HOST)")
@click.option("--port", default=None, type=int, help="Port to bind (overrides PROXAI_PORT)")
@click.option("--daemon", "-d", is_flag=True, help="Run in background")
@click.option("--env-file", default=".env", help="Path to .env file")
def start(host, port, daemon, env_file):
    """Start the ProxAI proxy server."""
    if Path(env_file).exists():
        load_dotenv(env_file)
    else:
        load_env()

    _host = host or os.getenv("PROXAI_HOST", "127.0.0.1")
    _port = port or int(os.getenv("PROXAI_PORT", "8090"))
    dashboard_enabled = os.getenv("PROXAI_DASHBOARD_ENABLED", "true").lower() == "true"
    dashboard_port = int(os.getenv("PROXAI_DASHBOARD_PORT", "8091"))

    click.echo(f"🚀 Starting ProxAI on http://{_host}:{_port}")

    if daemon:
        PID_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG_FILE, "a") as log:
            proc = subprocess.Popen(
                [sys.executable, "-m", "proxai._run",
                 "--host", _host, "--port", str(_port),
                 "--dashboard-port", str(dashboard_port)],
                stdout=log, stderr=log,
                start_new_session=True,
            )
        PID_FILE.write_text(str(proc.pid))
        click.echo(f"✅ ProxAI running (PID {proc.pid})")
        if dashboard_enabled:
            click.echo(f"📊 Dashboard: http://{_host}:{dashboard_port}")
    else:
        import uvicorn
        from .server import app
        if dashboard_enabled:
            click.echo(f"📊 Dashboard: http://{_host}:{dashboard_port}")
            _start_dashboard(_host, dashboard_port)
        uvicorn.run(app, host=_host, port=_port, log_level=os.getenv("PROXAI_LOG_LEVEL", "info").lower())


def _start_dashboard(host, port):
    """Start dashboard in background thread."""
    import threading
    import uvicorn
    from .dashboard.routes import dashboard_app

    def run():
        uvicorn.run(dashboard_app, host=host, port=port, log_level="warning")

    t = threading.Thread(target=run, daemon=True)
    t.start()


@cli.command()
def stop():
    """Stop the background ProxAI server."""
    if not PID_FILE.exists():
        click.echo("ProxAI is not running.")
        return
    pid = int(PID_FILE.read_text().strip())
    try:
        os.kill(pid, signal.SIGTERM)
        PID_FILE.unlink()
        click.echo(f"✅ Stopped ProxAI (PID {pid})")
    except ProcessLookupError:
        click.echo("ProxAI process not found (already stopped?)")
        PID_FILE.unlink(missing_ok=True)


@cli.command()
def status():
    """Show ProxAI server status."""
    if PID_FILE.exists():
        pid = int(PID_FILE.read_text().strip())
        try:
            os.kill(pid, 0)
            click.echo(f"✅ ProxAI is running (PID {pid})")
        except ProcessLookupError:
            click.echo("❌ ProxAI is not running (stale PID file)")
    else:
        click.echo("❌ ProxAI is not running")


@cli.command()
@click.option("--tail", "-n", default=50, help="Number of lines to show")
def logs(tail):
    """Show recent log output."""
    if not LOG_FILE.exists():
        click.echo("No log file found. Is ProxAI running in daemon mode?")
        return
    lines = LOG_FILE.read_text().splitlines()
    for line in lines[-tail:]:
        click.echo(line)


@cli.command()
@click.option("--days", default=30, help="Number of days to include")
def stats(days):
    """Show usage statistics."""
    from .db import get_stats, get_today_stats

    today = get_today_stats()
    monthly = get_stats(days=days)

    click.echo(f"\n📊 ProxAI Usage Stats\n{'─'*40}")
    click.echo(f"Today:   {today.get('requests',0)} requests  |  "
               f"{today.get('total_tokens',0):,} tokens  |  "
               f"${today.get('cost_usd',0):.4f}")
    click.echo(f"\nLast {days} days by provider:")
    for row in monthly:
        click.echo(
            f"  {row['provider']:<12}  {row['requests']:>5} req  "
            f"{(row['input_tokens']+row['output_tokens']):>8,} tok  "
            f"${row['cost_usd']:.4f}"
        )
    click.echo()


def main():
    cli()


if __name__ == "__main__":
    main()
