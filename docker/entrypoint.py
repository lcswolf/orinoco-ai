"""Expand Pterodactyl egg variables and exec the configured command.

Only simple command arguments are supported. Shell operators and shell
expansion are deliberately not evaluated.
"""

from __future__ import annotations

import os
import re
import shlex
import sys

PLACEHOLDER = re.compile(r"\{\{([A-Za-z_][A-Za-z0-9_]*)\}\}")


def main() -> int:
    startup = os.environ.get("STARTUP", "").strip()
    if not startup:
        print("ERROR: Pterodactyl did not provide STARTUP.", file=sys.stderr)
        return 2

    def replace(match: re.Match[str]) -> str:
        name = match.group(1)
        if name not in os.environ:
            print(f"ERROR: startup variable {name} is not set.", file=sys.stderr)
            raise SystemExit(2)
        return os.environ[name]

    try:
        command = PLACEHOLDER.sub(replace, startup)
        args = shlex.split(command)
    except ValueError as exc:
        print(f"ERROR: invalid STARTUP command: {exc}", file=sys.stderr)
        return 2

    if not args:
        print("ERROR: STARTUP resolved to an empty command.", file=sys.stderr)
        return 2

    os.execvp(args[0], args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
