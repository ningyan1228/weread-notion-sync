import argparse

from .config import load_settings
from .errors import ConfigError


def run_sync() -> None:
    settings = load_settings()

    from .notion_store import NotionStore
    from .sync import SyncEngine
    from .weread import WeReadClient

    weread = WeReadClient(settings.weread_api_key)
    notion = NotionStore(settings.notion_token, settings.notion_target)
    SyncEngine(weread=weread, notion=notion, full_sync=settings.full_sync).run()


def run_setup() -> None:
    settings = load_settings(require_weread=False)

    from .notion_store import create_template_database

    result = create_template_database(settings.notion_token, settings.notion_target)
    print("Notion 数据库已创建完成")
    print(f"DATABASE_ID={result.get('database_id')}")
    if result.get("data_source_id"):
        print(f"DATA_SOURCE_ID={result.get('data_source_id')}")
    if result.get("url"):
        print(f"URL={result.get('url')}")
    print("请把 NOTION_PAGE 更新为上面的 URL 或 DATABASE_ID，然后运行 weread-notion sync")


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(
        prog="weread-notion",
        description="Sync WeRead books, highlights and notes to Notion.",
    )
    parser.add_argument(
        "command",
        nargs="?",
        default="sync",
        choices=["sync", "setup"],
        help="Command to run. Defaults to sync.",
    )
    args = parser.parse_args(argv)

    try:
        if args.command == "setup":
            run_setup()
        else:
            run_sync()
    except ConfigError:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
