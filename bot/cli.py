"""Command-line entrypoint for running GenBot."""

from __future__ import annotations

import argparse
import importlib
import os
import shutil
from pathlib import Path


REQUIRED_ENV_VARS = ("TELEGRAM_BOT_TOKEN", "WALLET_ENCRYPTION_KEY")


def _load_dotenv_if_available() -> None:
    """Load local .env files before validating startup requirements."""
    try:
        from dotenv import load_dotenv
    except Exception:
        return

    project_root = Path(__file__).resolve().parents[1]
    load_dotenv(project_root / ".env", override=False)
    load_dotenv(override=False)


def _startup_issues() -> list[str]:
    issues: list[str] = []

    if shutil.which("genlayer") is None:
        issues.append("`genlayer` CLI is not installed or not in PATH.")

    for env_var in REQUIRED_ENV_VARS:
        if not os.environ.get(env_var):
            issues.append(f"`{env_var}` is not set.")

    return issues


def _print_check_result(issues: list[str]) -> int:
    if issues:
        print("GenBot startup check failed:")
        for issue in issues:
            print(f"- {issue}")
        return 1

    print("GenBot startup check passed.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="genbot",
        description="Run the GenBot Telegram bot for GenLayer contracts.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Validate env vars and the genlayer CLI without starting the bot.",
    )
    args = parser.parse_args(argv)

    _load_dotenv_if_available()
    issues = _startup_issues()

    if args.check or issues:
        return _print_check_result(issues)

    module = importlib.import_module("bot.main")
    module.main_cli()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
