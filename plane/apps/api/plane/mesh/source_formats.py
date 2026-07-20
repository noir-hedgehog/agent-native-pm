# Copyright (c) 2026-present Mesh contributors
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Any

import yaml


SKILL_VERSION_RE = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+(?:-[0-9A-Za-z.-]+)?$")
LOOP_NODE_TYPES = {"trigger", "stage", "gate", "approval", "handoff", "wait", "complete"}


@dataclass(frozen=True)
class ParsedSkill:
    manifest: dict[str, Any]
    body: str
    checksum: str


def parse_skill_markdown(source_text: str) -> ParsedSkill:
    normalized = source_text.replace("\r\n", "\n").strip() + "\n"
    if not normalized.startswith("---\n"):
        raise ValueError("SKILL.md must start with YAML front matter")
    marker = normalized.find("\n---\n", 4)
    if marker < 0:
        raise ValueError("SKILL.md front matter is not terminated with ---")
    manifest = yaml.safe_load(normalized[4:marker]) or {}
    if not isinstance(manifest, dict):
        raise ValueError("SKILL.md front matter must be a mapping")
    for field in ("name", "description"):
        if not str(manifest.get(field) or "").strip():
            raise ValueError(f"SKILL.md front matter requires {field}")
    version = str(manifest.get("version") or "0.1.0")
    if not SKILL_VERSION_RE.match(version):
        raise ValueError("SKILL.md version must use semantic versioning")
    manifest["version"] = version
    body = normalized[marker + 5 :].strip()
    if not body:
        raise ValueError("SKILL.md must contain a Markdown body")
    return ParsedSkill(manifest=manifest, body=body, checksum=sha256_text(normalized))


def parse_loop_yaml(source_text: str) -> dict[str, Any]:
    payload = yaml.safe_load(source_text)
    if not isinstance(payload, dict):
        raise ValueError("Loop YAML must be a mapping")
    if payload.get("schema_version") != 1:
        raise ValueError("Loop YAML schema_version must be 1")
    if not str(payload.get("name") or "").strip():
        raise ValueError("Loop YAML requires name")

    nodes = payload.get("nodes")
    if not isinstance(nodes, list) or not nodes:
        raise ValueError("Loop YAML requires at least one node")
    node_by_id: dict[str, dict[str, Any]] = {}
    for node in nodes:
        if not isinstance(node, dict):
            raise ValueError("Loop nodes must be mappings")
        node_id = str(node.get("id") or "").strip()
        node_type = str(node.get("type") or "").strip()
        if not node_id or node_id in node_by_id:
            raise ValueError(f"Loop node id is missing or duplicated: {node_id or '<empty>'}")
        if node_type not in LOOP_NODE_TYPES:
            raise ValueError(f"Unsupported Loop node type: {node_type}")
        if any(key in node for key in ("skill", "skills", "knowledge", "tool", "tools")):
            raise ValueError(f"Loop node {node_id} cannot prescribe skills, knowledge, or tools")
        if node_type == "stage":
            roles = node.get("roles")
            if not isinstance(roles, list) or not roles:
                raise ValueError(f"Stage node {node_id} requires at least one functional role")
            if not str(node.get("objective") or "").strip():
                raise ValueError(f"Stage node {node_id} requires objective")
        if node_type == "wait":
            duration = node.get("duration_seconds", 0)
            if not isinstance(duration, int) or duration < 0:
                raise ValueError(f"Wait node {node_id} duration_seconds must be a non-negative integer")
        node_by_id[node_id] = node

    triggers = [node for node in nodes if node["type"] == "trigger"]
    completes = [node for node in nodes if node["type"] == "complete"]
    if len(triggers) != 1:
        raise ValueError("Loop YAML requires exactly one trigger node")
    if not completes:
        raise ValueError("Loop YAML requires at least one complete node")

    edges = payload.get("edges")
    if not isinstance(edges, list) or not edges:
        raise ValueError("Loop YAML requires edges")
    adjacency = {node_id: [] for node_id in node_by_id}
    for edge in edges:
        if not isinstance(edge, dict):
            raise ValueError("Loop edges must be mappings")
        source = str(edge.get("from") or "")
        target = str(edge.get("to") or "")
        if source not in node_by_id or target not in node_by_id:
            raise ValueError(f"Loop edge references unknown node: {source}->{target}")
        adjacency[source].append(target)

    reachable = _reachable(adjacency, triggers[0]["id"])
    unreachable = sorted(set(node_by_id) - reachable)
    if unreachable:
        raise ValueError(f"Loop contains unreachable nodes: {', '.join(unreachable)}")
    for complete in completes:
        if adjacency[complete["id"]]:
            raise ValueError(f"Complete node {complete['id']} cannot have outgoing edges")

    if _contains_cycle(adjacency):
        limits = payload.get("limits") or {}
        max_transitions = limits.get("max_transitions") if isinstance(limits, dict) else None
        if not isinstance(max_transitions, int) or max_transitions <= 0:
            raise ValueError("Loop graphs with cycles require limits.max_transitions")

    return payload


def parse_project_policy_yaml(source_text: str, *, known_role_keys: set[str] | None = None) -> dict[str, Any]:
    payload = yaml.safe_load(source_text)
    if not isinstance(payload, dict):
        raise ValueError("Project Policy YAML must be a mapping")
    if payload.get("schema_version") != 1:
        raise ValueError("Project Policy schema_version must be 1")
    roles = payload.get("roles")
    if not isinstance(roles, dict) or not roles:
        raise ValueError("Project Policy requires a non-empty roles mapping")
    normalized_roles = {str(key).strip().lower() for key in roles}
    if known_role_keys is not None:
        unknown = sorted(normalized_roles - known_role_keys)
        if unknown:
            raise ValueError(f"Project Policy references unknown roles: {', '.join(unknown)}")
    for role_key, rule in roles.items():
        if not isinstance(rule, dict):
            raise ValueError(f"Policy role {role_key} must be a mapping")
        capabilities = rule.get("capabilities", [])
        if not isinstance(capabilities, list) or not all(isinstance(value, str) for value in capabilities):
            raise ValueError(f"Policy role {role_key} capabilities must be a string list")
    handoffs = payload.get("allowed_handoffs", {})
    if not isinstance(handoffs, dict):
        raise ValueError("Project Policy allowed_handoffs must be a mapping")
    for source, targets in handoffs.items():
        if str(source).lower() not in normalized_roles:
            raise ValueError(f"Project Policy handoff source is not a configured role: {source}")
        if not isinstance(targets, list) or not all(str(target).lower() in normalized_roles for target in targets):
            raise ValueError(f"Project Policy handoff targets for {source} must be configured role keys")
    delegation = payload.get("delegation", {})
    if delegation and not isinstance(delegation, dict):
        raise ValueError("Project Policy delegation must be a mapping")
    max_depth = delegation.get("max_depth", 1) if isinstance(delegation, dict) else 1
    if not isinstance(max_depth, int) or max_depth < 0:
        raise ValueError("Project Policy delegation.max_depth must be a non-negative integer")
    for key in ("budgets", "approvals"):
        if key in payload and not isinstance(payload[key], dict):
            raise ValueError(f"Project Policy {key} must be a mapping")
    return payload


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _reachable(adjacency: dict[str, list[str]], start: str) -> set[str]:
    pending = [start]
    visited: set[str] = set()
    while pending:
        node = pending.pop()
        if node in visited:
            continue
        visited.add(node)
        pending.extend(adjacency[node])
    return visited


def _contains_cycle(adjacency: dict[str, list[str]]) -> bool:
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node: str) -> bool:
        if node in visiting:
            return True
        if node in visited:
            return False
        visiting.add(node)
        if any(visit(target) for target in adjacency[node]):
            return True
        visiting.remove(node)
        visited.add(node)
        return False

    return any(visit(node) for node in adjacency)
