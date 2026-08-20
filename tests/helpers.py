from __future__ import annotations

import re
from pathlib import Path


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def skill_root() -> Path:
    return repo_root() / "skills" / "ppt-start"


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def parse_frontmatter(path: Path) -> dict[str, str]:
    lines = read_text(path).splitlines()
    if not lines or lines[0].strip() != "---":
        raise ValueError(f"{path} is missing opening frontmatter delimiter")

    try:
        closing = next(
            index for index, line in enumerate(lines[1:], start=1)
            if line.strip() == "---"
        )
    except StopIteration as exc:
        raise ValueError(f"{path} is missing closing frontmatter delimiter") from exc

    fields: dict[str, str] = {}
    for line in lines[1:closing]:
        if not line.strip():
            continue
        if ":" not in line:
            raise ValueError(f"Invalid frontmatter line in {path}: {line}")
        key, value = line.split(":", 1)
        fields[key.strip()] = value.strip().strip('"').strip("'")
    return fields


def relative_markdown_links(path: Path) -> list[Path]:
    links = re.findall(r"\[[^\]]+\]\(([^)]+)\)", read_text(path))
    resolved: list[Path] = []
    for link in links:
        target = link.split("#", 1)[0]
        if not target or "://" in target or target.startswith("mailto:"):
            continue
        resolved.append((path.parent / target).resolve())
    return resolved
