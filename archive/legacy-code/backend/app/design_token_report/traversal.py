from __future__ import annotations

from typing import Any


def walk_elements(root: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(root, dict):
        return []
    items: list[dict[str, Any]] = []

    def visit(node: dict[str, Any], path: str, parent_id: str | None) -> None:
        item = dict(node)
        item["_path"] = path
        item["_parentId"] = parent_id
        items.append(item)
        children = node.get("children")
        if not isinstance(children, list):
            return
        for index, child in enumerate(children):
            if isinstance(child, dict):
                visit(child, f"{path}.children[{index}]", str(node.get("id") or ""))

    visit(root, "root", None)
    return items


def visible_elements(elements: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [item for item in elements if is_visible(item)]


def is_visible(element: dict[str, Any]) -> bool:
    style = element.get("style") if isinstance(element.get("style"), dict) else {}
    if style.get("visible") is False:
        return False
    if element.get("role") == "original_reference":
        return False
    return True


def child_groups(root: dict[str, Any] | None) -> list[tuple[str, list[dict[str, Any]]]]:
    groups: list[tuple[str, list[dict[str, Any]]]] = []

    def visit(node: dict[str, Any], path: str) -> None:
        children = node.get("children")
        if isinstance(children, list):
            visible_children = [child for child in children if isinstance(child, dict) and is_visible(child)]
            if len(visible_children) >= 2:
                groups.append((path, visible_children))
            for index, child in enumerate(children):
                if isinstance(child, dict):
                    visit(child, f"{path}.children[{index}]")

    if isinstance(root, dict):
        visit(root, "root")
    return groups

