from __future__ import annotations

from dataclasses import replace

from .bbox import bbox_area, bbox_contains
from .types import LAYER_ORDER, M29PrimitiveNode, M29PrimitiveRelation


def build_containment_relations(nodes: list[M29PrimitiveNode]) -> list[M29PrimitiveRelation]:
    relations: list[M29PrimitiveRelation] = []
    containers = [node for node in nodes if node.type == "shape" and node.layer_hint in {"background", "container"}]
    children = [node for node in nodes if node.type in {"text", "image", "symbol"}]
    for child in children:
        parents = [container for container in containers if bbox_contains(container.bbox, child.bbox) and container.id != child.id]
        if not parents:
            continue
        parent = min(parents, key=lambda item: bbox_area(item.bbox))
        relations.append(M29PrimitiveRelation(parent.id, child.id, "contains", 0.72, ["bbox_contains"]))
    return relations

def attach_relation_children(nodes: list[M29PrimitiveNode], relations: list[M29PrimitiveRelation]) -> list[M29PrimitiveNode]:
    by_id = {node.id: node for node in nodes}
    children: dict[str, list[str]] = {}
    parent: dict[str, str] = {}
    for relation in relations:
        if relation.type == "contains":
            children.setdefault(relation.parent_id, []).append(relation.child_id)
            parent[relation.child_id] = relation.parent_id
    return [replace(node, parent_id=parent.get(node.id), child_ids=sorted(children.get(node.id, []))) for node in nodes]

def stable_sort_nodes(nodes: list[M29PrimitiveNode]) -> list[M29PrimitiveNode]:
    sorted_nodes = sorted(nodes, key=lambda item: (LAYER_ORDER[item.layer_hint], item.bbox[1], item.bbox[0], bbox_area(item.bbox)))
    return [replace(node, source_order=index) for index, node in enumerate(sorted_nodes)]
