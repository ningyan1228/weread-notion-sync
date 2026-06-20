from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .notion_blocks import callout, divider, heading, managed_blocks, paragraph, quote
from .notion_store import NotionStore
from .weread import (
    WeReadClient,
    format_duration,
    get_note_sort_key,
    web_reader_url,
)


BOOKMARK_ICON = "〰️"
THOUGHT_ICON = "✍️"


class SyncEngine:
    def __init__(self, weread: WeReadClient, notion: NotionStore, full_sync: bool = False):
        self.weread = weread
        self.notion = notion
        self.full_sync = full_sync

    def run(self) -> None:
        self.notion.connect()
        latest_sort = 0 if self.full_sync else self.notion.latest_sort()
        books = self.weread.notebooks()
        synced = 0

        print(f"微信读书笔记本共 {len(books)} 本，当前 Notion Sort 游标: {latest_sort}")
        for index, item in enumerate(books, start=1):
            sort = item.get("sort") or 0
            if sort <= latest_sort and not self.full_sync:
                continue

            book = item.get("book") or item
            book_id = book.get("bookId")
            title = book.get("title") or ""
            if not book_id or not title:
                continue

            print(f"正在同步 {title}，第 {index}/{len(books)} 本")
            self.sync_book(book=book, sort=sort)
            synced += 1

        print(f"同步完成，本次处理 {synced} 本书")

    def sync_book(self, book: Dict[str, Any], sort: int) -> None:
        book_id = str(book.get("bookId"))
        title = book.get("title") or ""
        author = book.get("author") or ""
        cover = normalize_cover(book.get("cover"))
        categories = extract_categories(book.get("categories"))

        read_info = self.weread.read_info(book_id)
        isbn, rating = self.weread.book_info(book_id)
        chapters = self.weread.chapters(book_id)
        bookmarks = self.weread.bookmarks(book_id)
        summaries, thoughts = self.weread.reviews(book_id)

        notes = [*bookmarks, *thoughts]
        notes = sorted(notes, key=lambda item: get_note_sort_key(item, chapters))
        children = self.build_page_children(chapters, notes, summaries)

        raw_properties = {
            self.notion.title_property: title,
            "BookId": book_id,
            "Sort": sort,
            "作者": author,
            "封面": cover,
            "状态": read_info.get("status"),
            "阅读进度": read_info.get("reading_progress"),
            "阅读时长": format_duration(read_info.get("reading_time") or 0),
            "分类": categories,
            "ISBN": isbn,
            "评分": rating,
            "微信读书链接": web_reader_url(book_id),
            "最后同步时间": datetime.now(timezone.utc),
            "划线数量": len(bookmarks),
            "想法数量": len(thoughts) + len(summaries),
        }

        page_id = self.notion.upsert_book_page(
            book_id=book_id,
            title=title,
            cover=cover,
            properties=raw_properties,
        )
        self.notion.replace_managed_children(page_id, managed_blocks(children))

    def build_page_children(
        self,
        chapters: Dict[Any, Dict[str, Any]],
        notes: List[Dict[str, Any]],
        summaries: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        children: List[Dict[str, Any]] = [
            paragraph("以下内容由 WeRead Notion Sync 自动同步。你可以在同步标记之外写自己的笔记。"),
            divider(),
        ]

        last_chapter_uid: Optional[Any] = None
        for note in notes:
            chapter_uid = note.get("chapterUid")
            if chapter_uid != last_chapter_uid:
                chapter = chapters.get(chapter_uid) or chapters.get(str(chapter_uid))
                if chapter:
                    level = int(chapter.get("level") or 1)
                    children.append(heading(level, chapter.get("title") or "未命名章节"))
                last_chapter_uid = chapter_uid

            text = note.get("markText") or ""
            if not text:
                continue

            icon = THOUGHT_ICON if note.get("_note_kind") == "thought" else BOOKMARK_ICON
            children.append(callout(text, icon=icon))
            abstract = note.get("abstract")
            if abstract:
                children.append(quote(abstract))

        if summaries:
            children.append(heading(1, "点评"))
            for item in summaries:
                content = (item.get("review") or {}).get("content") or ""
                if content:
                    children.append(callout(content, icon=THOUGHT_ICON))

        return children


def normalize_cover(value: Any) -> Optional[str]:
    cover = str(value or "")
    if not cover:
        return None
    if cover.startswith("http"):
        return cover.replace("/s_", "/t7_")
    return None


def extract_categories(value: Any) -> List[str]:
    if not value:
        return []
    categories = []
    for item in value:
        if isinstance(item, dict) and item.get("title"):
            categories.append(str(item["title"]))
        elif item:
            categories.append(str(item))
    return categories
