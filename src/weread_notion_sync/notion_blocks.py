from typing import Any, Dict, Iterable, List, Optional


BEGIN_MARKER = "--- weread-notion-sync:begin ---"
END_MARKER = "--- weread-notion-sync:end ---"


def text_rich(content: str) -> List[Dict[str, Any]]:
    return [{"type": "text", "text": {"content": content[:2000]}}]


def paragraph(content: str) -> Dict[str, Any]:
    return {"type": "paragraph", "paragraph": {"rich_text": text_rich(content)}}


def heading(level: int, content: str) -> Dict[str, Any]:
    block_type = "heading_1" if level == 1 else "heading_2" if level == 2 else "heading_3"
    return {
        "type": block_type,
        block_type: {
            "rich_text": text_rich(content),
            "color": "default",
            "is_toggleable": False,
        },
    }


def callout(content: str, icon: str = "〰️") -> Dict[str, Any]:
    return {
        "type": "callout",
        "callout": {
            "rich_text": text_rich(content),
            "icon": {"type": "emoji", "emoji": icon},
        },
    }


def quote(content: str) -> Dict[str, Any]:
    return {
        "type": "quote",
        "quote": {
            "rich_text": text_rich(content),
            "color": "default",
        },
    }


def divider() -> Dict[str, Any]:
    return {"type": "divider", "divider": {}}


def chunk_text(content: str, size: int = 1900) -> Iterable[str]:
    text = content or ""
    if not text:
        return
    for index in range(0, len(text), size):
        yield text[index : index + size]


def plain_text(block: Dict[str, Any]) -> str:
    block_type = block.get("type")
    value = block.get(block_type or "") or {}
    rich = value.get("rich_text") or []
    return "".join(part.get("plain_text") or "" for part in rich)


def managed_blocks(children: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [
        paragraph(BEGIN_MARKER),
        *children,
        paragraph(END_MARKER),
    ]


def icon_external(url: Optional[str]) -> Optional[Dict[str, Any]]:
    if not url:
        return None
    return {"type": "external", "external": {"url": url}}
