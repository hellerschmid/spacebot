import asyncio

from spacebot.bot import main as async_main


def main() -> None:
    """Synchronous entry point for the console_scripts entrypoint."""
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
