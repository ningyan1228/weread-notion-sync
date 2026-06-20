import hashlib
import re
from typing import Any, Dict, Iterable, List, Optional, Tuple

import requests
from retrying import retry


WEREAD_GATEWAY_URL = "https://i.weread.qq.com/api/agent/gateway"
WEREAD_SKILL_VERSION = "1.0.3"


class WeReadClient:
    def __init__(self, api_key: str):
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }
        )

    @retry(stop_max_attempt_number=3, wait_fixed=5000)
    def request(self, api_name: str, **params: Any) -> Dict[str, Any]:
        payload = {
            "api_name": api_name,
            "skill_version": WEREAD_SKILL_VERSION,
            **params,
        }
        response = self.session.post(WEREAD_GATEWAY_URL, json=payload, timeout=30)
        response.raise_for_status()
        data = response.json()
        if data.get("upgrade_info"):
            raise RuntimeError(f"微信读书 skill 需要升级: {data.get('upgrade_info')}")
        if data.get("errcode", 0) != 0:
            raise RuntimeError(
                f"微信读书 Gateway 请求失败: {api_name}, "
                f"errcode={data.get('errcode')}, response={data}"
            )
        return data

    def notebooks(self) -> List[Dict[str, Any]]:
        books: List[Dict[str, Any]] = []
        has_more = 1
        last_sort: Optional[int] = None
        while has_more:
            params: Dict[str, Any] = {"count": 100}
            if last_sort is not None:
                params["lastSort"] = last_sort
            data = self.request("/user/notebooks", **params)
            batch = data.get("books") or []
            books.extend(batch)
            has_more = data.get("hasMore", 0)
            last_sort = batch[-1].get("sort") if batch else None
            if not batch:
                break
        return sorted(books, key=lambda item: item.get("sort") or 0)

    def book_info(self, book_id: str) -> Tuple[str, Optional[float]]:
        data = self.request("/book/info", bookId=book_id)
        return data.get("isbn", ""), normalize_rating(data.get("newRating"))

    def read_info(self, book_id: str) -> Dict[str, Any]:
        data = self.request("/book/getprogress", bookId=book_id)
        book = data.get("book") or {}
        progress = to_number(book.get("progress")) or 0
        finish_time = book.get("finishTime") or 0
        update_time = book.get("updateTime") or 0

        if finish_time or progress >= 100:
            status = "读完"
        elif update_time or book.get("isStartReading") or progress > 0:
            status = "在读"
        else:
            status = "未读"

        return {
            "status": status,
            "reading_time": book.get("recordReadingTime") or 0,
            "reading_progress": normalize_reading_progress(progress),
            "finished_at": finish_time,
        }

    def chapters(self, book_id: str) -> Dict[Any, Dict[str, Any]]:
        data = self.request("/book/chapterinfo", bookId=book_id)
        chapters = data.get("chapters") or []
        return {item["chapterUid"]: item for item in chapters if "chapterUid" in item}

    def bookmarks(self, book_id: str) -> List[Dict[str, Any]]:
        data = self.request("/book/bookmarklist", bookId=book_id)
        updated = data.get("updated") or []
        return sorted(updated, key=get_note_sort_key)

    def reviews(self, book_id: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        reviews_data: List[Dict[str, Any]] = []
        has_more = 1
        synckey = 0
        while has_more:
            data = self.request("/review/list/mine", bookid=book_id, synckey=synckey, count=100)
            batch = data.get("reviews") or []
            reviews_data.extend(batch)
            has_more = data.get("hasMore", 0)
            synckey = data.get("synckey", 0)
            if not batch:
                break

        summaries = [
            item for item in reviews_data if (item.get("review") or {}).get("type") == 4
        ]
        notes = [
            {
                **(item.get("review") or {}),
                "markText": (item.get("review") or {}).get("content", ""),
                "_note_kind": "thought",
            }
            for item in reviews_data
            if (item.get("review") or {}).get("type") == 1
        ]
        return summaries, notes


def to_number(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return value
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return int(number) if number.is_integer() else number


def normalize_reading_progress(value: Any) -> float:
    progress = to_number(value) or 0
    if progress > 1:
        progress = progress / 100
    return round(min(max(progress, 0), 1), 4)


def normalize_rating(value: Any) -> Optional[float]:
    rating = to_number(value)
    if rating is None:
        return None
    if rating > 100:
        return rating / 1000
    if rating > 10:
        return rating / 10
    return rating


def range_start(item: Dict[str, Any]) -> int:
    note_range = item.get("range") or ""
    try:
        return int(str(note_range).split("-")[0] or 0)
    except (TypeError, ValueError):
        return 0


def get_note_sort_key(item: Dict[str, Any], chapters: Optional[Dict[Any, Dict[str, Any]]] = None):
    chapter_uid = item.get("chapterUid", 1)
    chapter = None
    if chapters:
        chapter = chapters.get(chapter_uid) or chapters.get(str(chapter_uid))
    chapter_idx = chapter.get("chapterIdx", 1000000) if chapter else chapter_uid
    return (chapter_idx, range_start(item))


def format_duration(seconds: int) -> str:
    seconds = int(seconds or 0)
    hours = seconds // 3600
    minutes = seconds % 3600 // 60
    parts = []
    if hours:
        parts.append(f"{hours}时")
    if minutes:
        parts.append(f"{minutes}分")
    return "".join(parts) or "0分"


def transform_book_id(book_id: str) -> Tuple[str, List[str]]:
    if re.match(r"^\d*$", book_id):
        chunks = [format(int(book_id[i : min(i + 9, len(book_id))]), "x") for i in range(0, len(book_id), 9)]
        return "3", chunks

    result = "".join(format(ord(char), "x") for char in book_id)
    return "4", [result]


def web_reader_url(book_id: str) -> str:
    digest = hashlib.md5(book_id.encode("utf-8")).hexdigest()
    result = digest[0:3]
    code, transformed_ids = transform_book_id(book_id)
    result += code + "2" + digest[-2:]

    for index, transformed_id in enumerate(transformed_ids):
        hex_length = format(len(transformed_id), "x")
        if len(hex_length) == 1:
            hex_length = "0" + hex_length
        result += hex_length + transformed_id
        if index < len(transformed_ids) - 1:
            result += "g"

    if len(result) < 20:
        result += digest[0 : 20 - len(result)]

    tail = hashlib.md5(result.encode("utf-8")).hexdigest()[0:3]
    return f"https://weread.qq.com/web/reader/{result}{tail}"
