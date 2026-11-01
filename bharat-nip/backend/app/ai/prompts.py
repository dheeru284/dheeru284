"""Versioned, hashed prompt templates (AI_AGENT_ARCHITECTURE.md §4).

File layout: ``<root>/<prompt_id>/<version>.md``. Each file starts with YAML
front-matter (``prompt_id``, ``version``, ``agent``, ``description``) between
``---`` lines, followed by the template body. Placeholders are ``{{name}}``.
``sha256`` is computed over the exact file bytes, so any edit changes the hash.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import yaml

from app.core.hashing import sha256_text

DEFAULT_PROMPT_ROOT = Path(__file__).resolve().parent.parent / "prompts"
_PLACEHOLDER = re.compile(r"\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}")
_VERSION = re.compile(r"^v\d+$")


class PromptError(Exception):
    pass


@dataclass(frozen=True)
class PromptTemplate:
    prompt_id: str
    version: str
    agent: str
    description: str
    body: str
    sha256: str

    @property
    def placeholders(self) -> set[str]:
        return set(_PLACEHOLDER.findall(self.body))

    def render(self, **variables: str) -> str:
        missing = self.placeholders - variables.keys()
        extra = variables.keys() - self.placeholders
        if missing or extra:
            raise PromptError(
                f"{self.prompt_id}/{self.version}: missing={sorted(missing)} extra={sorted(extra)}"
            )
        return _PLACEHOLDER.sub(lambda m: variables[m.group(1)], self.body)


def parse_prompt_file(path: Path) -> PromptTemplate:
    raw = path.read_text(encoding="utf-8")
    if not raw.startswith("---\n"):
        raise PromptError(f"{path}: missing front-matter")
    try:
        _, front, body = raw.split("---\n", 2)
    except ValueError as exc:
        raise PromptError(f"{path}: unterminated front-matter") from exc
    meta = yaml.safe_load(front) or {}
    for key in ("prompt_id", "version", "agent", "description"):
        if not meta.get(key):
            raise PromptError(f"{path}: front-matter missing '{key}'")
    if meta["prompt_id"] != path.parent.name or meta["version"] != path.stem:
        raise PromptError(f"{path}: prompt_id/version must match directory/file name")
    if not _VERSION.match(meta["version"]):
        raise PromptError(f"{path}: version must look like 'v1'")
    return PromptTemplate(
        prompt_id=meta["prompt_id"],
        version=meta["version"],
        agent=meta["agent"],
        description=meta["description"],
        body=body.lstrip("\n"),
        sha256=sha256_text(raw),
    )


class PromptRegistry:
    def __init__(self, root: Path = DEFAULT_PROMPT_ROOT) -> None:
        self._templates: dict[tuple[str, str], PromptTemplate] = {}
        for path in sorted(root.glob("*/v*.md")):
            tpl = parse_prompt_file(path)
            self._templates[(tpl.prompt_id, tpl.version)] = tpl

    def get(self, prompt_id: str, version: str) -> PromptTemplate:
        try:
            return self._templates[(prompt_id, version)]
        except KeyError as exc:
            raise PromptError(f"Unknown prompt {prompt_id}/{version}") from exc

    def versions(self, prompt_id: str) -> list[str]:
        return sorted(
            (v for (pid, v) in self._templates if pid == prompt_id), key=lambda v: int(v[1:])
        )

    def all(self) -> list[PromptTemplate]:
        return list(self._templates.values())


def wrap_untrusted(kind: str, block_id: str, text: str) -> str:
    """Delimit untrusted text (submissions, source chunks) as data.

    Delimiter look-alikes inside the text are neutralised so content cannot close
    the block early and smuggle in instructions.
    """
    safe = text.replace("<<<", "\u2039" * 3).replace(">>>", "\u203a" * 3)
    return f"<<<{kind} id={block_id}>>>\n{safe}\n<<<END {kind}>>>"
