import time
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Tuple

from notion_client import Client
from notion_client.errors import APIResponseError

from .config import extract_notion_id
from .notion_blocks import BEGIN_MARKER, END_MARKER, icon_external, plain_text


NOTION_VERSION = "2026-03-11"


TEMPLATE_PROPERTIES: Dict[str, Any] = {
    "书名": {"title": {}},
    "BookId": {"rich_text": {}},
    "Sort": {"number": {"format": "number"}},
    "作者": {"rich_text": {}},
    "封面": {"url": {}},
    "状态": {
        "select": {
            "options": [
                {"name": "在读", "color": "blue"},
                {"name": "读完", "color": "green"},
                {"name": "未读", "color": "gray"},
            ]
        }
    },
    "阅读进度": {"number": {"format": "percent"}},
    "阅读时长": {"rich_text": {}},
    "分类": {"multi_select": {}},
    "ISBN": {"rich_text": {}},
    "评分": {"number": {"format": "number"}},
    "微信读书链接": {"url": {}},
    "最后同步时间": {"date": {}},
    "划线数量": {"number": {"format": "number"}},
    "想法数量": {"number": {"format": "number"}},
}


class NotionStore:
    def __init__(self, token: str, target: str):
        self.client = Client(auth=token, notion_version=NOTION_VERSION)
        self.target_id = extract_notion_id(target)
        self.data_source_id = ""
        self.property_types: Dict[str, str] = {}
        self.title_property = ""
        self.skipped_properties = set()

    def connect(self) -> None:
        self.data_source_id = self._resolve_data_source_id(self.target_id)
        self._load_schema()
        print(f"Notion API Version: {NOTION_VERSION}")
        print(f"Notion Data Source ID: {self.data_source_id}")
        print(f"已读取 Notion 属性 {len(self.property_types)} 个，标题属性: {self.title_property}")

    def _resolve_data_source_id(self, notion_id: str) -> str:
        try:
            self.client.request(path=f"data_sources/{notion_id}", method="GET")
            return notion_id
        except APIResponseError as error:
            code = getattr(error.code, "value", error.code)
            if code not in {"object_not_found", "validation_error"}:
                raise

        database = self.client.request(path=f"databases/{notion_id}", method="GET")
        sources = database.get("data_sources") or []
        if not sources:
            raise RuntimeError(f"数据库 {notion_id} 下没有可用的 data source")
        if len(sources) > 1:
            print(f"数据库包含 {len(sources)} 个 data sources，默认使用第一个: {sources[0].get('id')}")
        return sources[0]["id"]

    def _load_schema(self) -> None:
        response = self.client.request(path=f"data_sources/{self.data_source_id}", method="GET")
        properties = response.get("properties") or {}
        self.property_types = {
            name: (config or {}).get("type") for name, config in properties.items()
        }
        self.title_property = next(
            (name for name, prop_type in self.property_types.items() if prop_type == "title"),
            "",
        )
        if not self.title_property:
            raise RuntimeError("Notion 数据库缺少 Title 类型属性")

        missing = [name for name in ("BookId", "Sort") if name not in self.property_types]
        if missing:
            raise RuntimeError(f"Notion 数据库缺少必填属性: {', '.join(missing)}")

    def latest_sort(self) -> float:
        response = self.query(
            filter=self._is_not_empty_filter("Sort"),
            sorts=[{"property": "Sort", "direction": "descending"}],
            page_size=1,
        )
        results = response.get("results") or []
        if not results:
            return 0
        return self._number_from_property(results[0].get("properties", {}).get("Sort"))

    def find_book_page(self, book_id: str) -> Optional[Dict[str, Any]]:
        response = self.query(filter=self._equals_filter("BookId", book_id), page_size=1)
        results = response.get("results") or []
        return results[0] if results else None

    def upsert_book_page(
        self,
        book_id: str,
        title: str,
        cover: Optional[str],
        properties: Dict[str, Any],
    ) -> str:
        page = self.find_book_page(book_id)
        notion_properties = self.build_properties(properties)
        icon = icon_external(cover)
        cover_value = icon_external(cover)

        if page:
            body: Dict[str, Any] = {"page_id": page["id"], "properties": notion_properties}
            if icon:
                body["icon"] = icon
            if cover_value:
                body["cover"] = cover_value
            self.client.pages.update(**body)
            return page["id"]

        body = {
            "parent": {"type": "data_source_id", "data_source_id": self.data_source_id},
            "properties": notion_properties,
        }
        if icon:
            body["icon"] = icon
            body["cover"] = icon
        response = self.client.pages.create(**body)
        return response["id"]

    def replace_managed_children(self, page_id: str, children: List[Dict[str, Any]]) -> None:
        existing = self.list_children(page_id)
        begin, end = self._managed_range(existing)
        if begin is not None and end is not None:
            for block in existing[begin : end + 1]:
                self.client.blocks.delete(block_id=block["id"])
                time.sleep(0.15)
        self.append_children(page_id, children)

    def append_children(self, block_id: str, children: List[Dict[str, Any]]) -> None:
        for index in range(0, len(children), 100):
            batch = children[index : index + 100]
            if batch:
                self.client.blocks.children.append(block_id=block_id, children=batch)
                time.sleep(0.3)

    def list_children(self, block_id: str) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        start_cursor = None
        while True:
            kwargs: Dict[str, Any] = {"block_id": block_id, "page_size": 100}
            if start_cursor:
                kwargs["start_cursor"] = start_cursor
            response = self.client.blocks.children.list(**kwargs)
            results.extend(response.get("results") or [])
            if not response.get("has_more"):
                return results
            start_cursor = response.get("next_cursor")

    def _managed_range(self, blocks: List[Dict[str, Any]]) -> Tuple[Optional[int], Optional[int]]:
        begin = None
        end = None
        for index, block in enumerate(blocks):
            text = plain_text(block).strip()
            if text == BEGIN_MARKER:
                begin = index
            elif text == END_MARKER and begin is not None:
                end = index
                break
        return begin, end

    def query(self, **body: Any) -> Dict[str, Any]:
        return self.client.request(
            path=f"data_sources/{self.data_source_id}/query",
            method="POST",
            body=body,
        )

    def build_properties(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        properties = {}
        for name, value in raw.items():
            prop = self._build_property(name, value)
            if prop is not None:
                properties[name] = prop
        return properties

    def _build_property(self, name: str, value: Any) -> Optional[Dict[str, Any]]:
        prop_type = self.property_types.get(name)
        if not prop_type:
            if name not in self.skipped_properties:
                print(f"属性 {name} 在 Notion 数据库中不存在，自动跳过")
                self.skipped_properties.add(name)
            return None
        if value is None:
            return None

        if prop_type == "title":
            return {"title": [{"type": "text", "text": {"content": str(value)}}]}
        if prop_type == "rich_text":
            return {"rich_text": [{"type": "text", "text": {"content": str(value)}}]}
        if prop_type == "number":
            number = _to_number(value)
            return {"number": number} if number is not None else None
        if prop_type == "url":
            return {"url": str(value)}
        if prop_type == "date":
            return {"date": {"start": _to_date(value)}}
        if prop_type == "checkbox":
            return {"checkbox": bool(value)}
        if prop_type == "select":
            names = _to_names(value)
            return {"select": {"name": names[0]}} if names else None
        if prop_type == "status":
            names = _to_names(value)
            return {"status": {"name": names[0]}} if names else None
        if prop_type == "multi_select":
            return {"multi_select": [{"name": name} for name in _to_names(value)]}
        if prop_type == "files":
            return {
                "files": [
                    {
                        "type": "external",
                        "name": "Cover",
                        "external": {"url": str(value)},
                    }
                ]
            }

        if name not in self.skipped_properties:
            print(f"属性 {name} 的类型 {prop_type} 暂不支持写入，自动跳过")
            self.skipped_properties.add(name)
        return None

    def _equals_filter(self, name: str, value: Any) -> Dict[str, Any]:
        prop_type = self.property_types.get(name)
        if prop_type in {"title", "rich_text", "url", "email", "phone_number"}:
            return {"property": name, prop_type: {"equals": str(value)}}
        if prop_type == "number":
            return {"property": name, "number": {"equals": _to_number(value)}}
        if prop_type == "select":
            return {"property": name, "select": {"equals": str(value)}}
        if prop_type == "status":
            return {"property": name, "status": {"equals": str(value)}}
        raise RuntimeError(f"Notion 属性 {name} 的类型 {prop_type} 暂不支持用于查询")

    def _is_not_empty_filter(self, name: str) -> Dict[str, Any]:
        prop_type = self.property_types.get(name)
        if prop_type in {
            "title",
            "rich_text",
            "url",
            "email",
            "phone_number",
            "number",
            "select",
            "status",
            "date",
        }:
            return {"property": name, prop_type: {"is_not_empty": True}}
        raise RuntimeError(f"Notion 属性 {name} 的类型 {prop_type} 暂不支持用于查询")

    def _number_from_property(self, property_value: Optional[Dict[str, Any]]) -> float:
        if not property_value:
            return 0
        prop_type = property_value.get("type")
        value = property_value.get(prop_type or "")
        if prop_type == "number":
            return _to_number(value) or 0
        if prop_type in {"title", "rich_text"} and value:
            return _to_number(value[0].get("plain_text")) or 0
        if prop_type in {"select", "status"} and value:
            return _to_number(value.get("name")) or 0
        return 0


def _to_number(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return value
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return int(number) if number.is_integer() else number


def _to_names(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        return [str(item) for item in value if str(item)]
    text = str(value)
    return [text] if text else []


def _to_date(value: Any) -> str:
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=timezone.utc).isoformat()
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def create_template_database(token: str, parent_page: str) -> Dict[str, Any]:
    client = Client(auth=token, notion_version=NOTION_VERSION)
    parent_page_id = extract_notion_id(parent_page)
    body = {
        "parent": {"type": "page_id", "page_id": parent_page_id},
        "title": [{"type": "text", "text": {"content": "微信读书笔记"}}],
        "is_inline": True,
        "initial_data_source": {
            "title": [{"type": "text", "text": {"content": "微信读书"}}],
            "properties": TEMPLATE_PROPERTIES,
        },
        "icon": {"type": "emoji", "emoji": "📘"},
    }
    response = client.request(path="databases", method="POST", body=body)
    database_id = response.get("id")
    data_sources = response.get("data_sources") or []
    data_source_id = data_sources[0].get("id") if data_sources else None
    return {
        "database_id": database_id,
        "data_source_id": data_source_id,
        "url": response.get("url"),
    }
