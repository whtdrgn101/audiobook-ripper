"""Entry point for the audiobook ripper application."""

import sys


def main() -> int:
    """Main entry point."""
    from audiobook_ripper.app import create_app
    app = create_app()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
