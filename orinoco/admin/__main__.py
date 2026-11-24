"""Enable the `python -m orinoco.admin` first-admin setup command."""

from orinoco.admin.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
