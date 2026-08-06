#!/usr/bin/env python3
"""
generate_index.py

Automatically generates a beautiful, fully-automatic `index.md` for the
repository it lives in. Designed to be run from GitHub Actions on every
push, with zero configuration required.

Usage:
    python scripts/generate_index.py

Author: Auto-generated tooling.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from zoneinfo import ZoneInfo

# --------------------------------------------------------------------------
# Configuration (zero manual configuration required -- everything here is
# purely structural: what to ignore, not what to include).
# --------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent
INDEX_FILENAME = "index.md"
TIMEZONE = "Asia/Dhaka"

IGNORE_DIR_NAMES = {
    ".git",
    ".github",
    "scripts",
    "__pycache__",
    "node_modules",
    ".venv",
    "venv",
    ".vscode",
    ".idea",
    ".cache",
}

IGNORE_FILE_NAMES = {
    "index.md",
    "generate_index.py",
    "update-index.yml",
}

TEMP_FILE_SUFFIXES = (".tmp", ".swp", ".swo", ".bak", "~")

MARKDOWN_SUFFIX = ".md"

EMOJI = {
    "book": "📚",
    "folder": "📂",
    "folder_alt": "📁",
    "file": "📄",
    "tree": "🌳",
    "stats": "📊",
    "clock": "🕒",
    "link": "🔗",
    "robot": "🤖",
}


# --------------------------------------------------------------------------
# Data structures
# --------------------------------------------------------------------------

@dataclass
class DirNode:
    """A single directory in the scanned repository tree."""

    name: str
    rel_path: Path
    files: List[str] = field(default_factory=list)
    subdirs: Dict[str, "DirNode"] = field(default_factory=dict)

    @property
    def markdown_files(self) -> List[str]:
        return [f for f in self.files if f.lower().endswith(MARKDOWN_SUFFIX)]


@dataclass
class RepoStats:
    total_folders: int = 0
    total_files: int = 0
    markdown_files: int = 0
    documentation_folders: int = 0
    total_size_bytes: int = 0


# --------------------------------------------------------------------------
# Filesystem helpers
# --------------------------------------------------------------------------

def is_hidden(name: str) -> bool:
    return name.startswith(".")


def is_temp_file(name: str) -> bool:
    return name.endswith(TEMP_FILE_SUFFIXES)


def should_ignore_dir(name: str) -> bool:
    return name in IGNORE_DIR_NAMES or is_hidden(name)


def should_ignore_file(name: str) -> bool:
    if name in IGNORE_FILE_NAMES:
        return True
    if is_hidden(name):
        return True
    if is_temp_file(name):
        return True
    return False


def sort_key_files(filename: str) -> tuple:
    """README.md always first, then alphabetical, case-insensitive."""
    is_readme = filename.lower() != "readme.md"
    return (is_readme, filename.lower())


def sort_key_dirs(name: str) -> str:
    return name.lower()


# --------------------------------------------------------------------------
# Scanning
# --------------------------------------------------------------------------

def scan_repository(root: Path) -> DirNode:
    """
    Recursively scans the repository, skipping ignored directories entirely
    (for performance, ignored directories are pruned before os.walk
    descends into them).
    """
    root_node = DirNode(name=root.name, rel_path=Path("."))
    node_index: Dict[Path, DirNode] = {Path("."): root_node}

    for current_dir, dirnames, filenames in os.walk(root):
        current_path = Path(current_dir)
        try:
            rel_current = current_path.relative_to(root)
        except ValueError:
            continue

        # Prune ignored directories in-place so os.walk never descends
        # into them -- this keeps the scan efficient on large repos.
        dirnames[:] = sorted(
            (d for d in dirnames if not should_ignore_dir(d)),
            key=sort_key_dirs,
        )

        parent_node = node_index.get(rel_current)
        if parent_node is None:
            # Should not normally happen, but guard defensively.
            continue

        for dirname in dirnames:
            child_rel = rel_current / dirname
            child_node = DirNode(name=dirname, rel_path=child_rel)
            parent_node.subdirs[dirname] = child_node
            node_index[child_rel] = child_node

        try:
            for filename in sorted(filenames):
                try:
                    if should_ignore_file(filename):
                        continue
                    full_path = current_path / filename
                    if not full_path.is_file():
                        continue
                    parent_node.files.append(filename)
                except (PermissionError, OSError):
                    continue
        except (PermissionError, OSError):
            continue

    return root_node


# --------------------------------------------------------------------------
# Statistics
# --------------------------------------------------------------------------

def compute_stats(root: Path, root_node: DirNode) -> RepoStats:
    stats = RepoStats()

    def walk(node: DirNode, is_root: bool) -> None:
        if not is_root:
            stats.total_folders += 1
        md_count_here = len(node.markdown_files)
        if md_count_here > 0:
            stats.documentation_folders += 1

        for filename in node.files:
            stats.total_files += 1
            if filename.lower().endswith(MARKDOWN_SUFFIX):
                stats.markdown_files += 1
            try:
                full_path = root / node.rel_path / filename
                stats.total_size_bytes += full_path.stat().st_size
            except (PermissionError, OSError):
                pass

        for child in node.subdirs.values():
            walk(child, is_root=False)

    walk(root_node, is_root=True)
    return stats


def human_readable_size(num_bytes: int) -> str:
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024.0:
            return f"{size:.1f} {unit}" if unit != "B" else f"{int(size)} {unit}"
        size /= 1024.0
    return f"{size:.1f} PB"


def current_timestamp() -> str:
    now = datetime.now(ZoneInfo(TIMEZONE))
    date_part = now.strftime("%d %B %Y")
    time_part = now.strftime("%I:%M %p").lstrip("0") or "12:00 AM"
    return f"{date_part}  \n{time_part} ({TIMEZONE})"


# --------------------------------------------------------------------------
# Markdown link helpers
# --------------------------------------------------------------------------

def md_link(label: str, rel_path: Path) -> str:
    href = str(rel_path).replace(os.sep, "/")
    return f"[{label}]({href})"


def anchor(text: str) -> str:
    slug = "".join(
        ch.lower() if ch.isalnum() or ch in " -" else "" for ch in text
    ).strip()
    slug = slug.replace(" ", "-")
    return f"#{slug}"


# --------------------------------------------------------------------------
# Section builders
# --------------------------------------------------------------------------

def build_header() -> str:
    return f"> {EMOJI['robot']} Automatically generated.\n> Do not edit manually.\n"


def build_title() -> str:
    return f"# {EMOJI['book']} Repository Index\n"


def build_toc() -> str:
    entries = [
        f"{EMOJI['stats']} Statistics",
        f"{EMOJI['book']} Documentation",
        f"{EMOJI['tree']} Repository Tree",
        f"{EMOJI['file']} Root Files",
        f"{EMOJI['link']} Quick Links",
    ]
    lines = ["## Table of Contents\n"]
    for entry in entries:
        lines.append(f"- [{entry}]({anchor(entry)})")
    return "\n".join(lines) + "\n"


def build_statistics_section(stats: RepoStats) -> str:
    lines = [f"## {EMOJI['stats']} Statistics\n"]
    lines.append("| Metric | Count |")
    lines.append("|---|---|")
    lines.append(f"| Folders | {stats.total_folders} |")
    lines.append(f"| Files | {stats.total_files} |")
    lines.append(f"| Markdown Files | {stats.markdown_files} |")
    lines.append(f"| Documentation Folders | {stats.documentation_folders} |")
    lines.append(f"| Repository Size | {human_readable_size(stats.total_size_bytes)} |")
    lines.append("")
    lines.append(f"**{EMOJI['clock']} Last Updated**")
    lines.append("")
    lines.append(current_timestamp())
    return "\n".join(lines) + "\n"


def build_documentation_section(root_node: DirNode) -> str:
    lines = [f"## {EMOJI['book']} Documentation\n"]

    doc_folders: List[DirNode] = []

    def collect(node: DirNode, is_root: bool) -> None:
        if node.markdown_files:
            doc_folders.append(node)
        for child in sorted(node.subdirs.values(), key=lambda n: sort_key_dirs(n.name)):
            collect(child, is_root=False)

    collect(root_node, is_root=True)

    if not doc_folders:
        lines.append("_No documentation found in this repository yet._")
        return "\n".join(lines) + "\n"

    for node in doc_folders:
        label = "Root" if node.rel_path == Path(".") else str(node.rel_path).replace(os.sep, "/")
        lines.append(f"### {EMOJI['folder']} {label}\n")
        for filename in sorted(node.markdown_files, key=sort_key_files):
            file_rel = node.rel_path / filename if node.rel_path != Path(".") else Path(filename)
            lines.append(f"- {md_link(filename, file_rel)}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def build_tree_section(root_node: DirNode) -> str:
    lines = [f"## {EMOJI['tree']} Repository Tree\n"]

    def render(node: DirNode, prefix: str) -> None:
        children_dirs = sorted(node.subdirs.values(), key=lambda n: sort_key_dirs(n.name))
        files = sorted(node.files, key=sort_key_files)
        entries: List[tuple] = [("dir", c) for c in children_dirs] + [("file", f) for f in files]

        for index, (kind, item) in enumerate(entries):
            is_last = index == len(entries) - 1
            connector = "└── " if is_last else "├── "
            if kind == "dir":
                dir_node: DirNode = item
                lines.append(f"{prefix}{connector}{EMOJI['folder_alt']} {dir_node.name}")
                extension = "    " if is_last else "│   "
                render(dir_node, prefix + extension)
            else:
                filename: str = item
                file_rel = node.rel_path / filename if node.rel_path != Path(".") else Path(filename)
                lines.append(f"{prefix}{connector}{md_link(filename, file_rel)}")

    if not root_node.subdirs and not root_node.files:
        lines.append("_This repository is currently empty._")
    else:
        lines.append(f"{EMOJI['folder_alt']} {root_node.name}/")
        render(root_node, "")

    return "\n".join(lines) + "\n"


def build_root_files_section(root_node: DirNode) -> str:
    lines = [f"## {EMOJI['file']} Root Files\n"]
    if not root_node.files:
        lines.append("_No root-level files found._")
        return "\n".join(lines) + "\n"

    for filename in sorted(root_node.files, key=sort_key_files):
        lines.append(f"- {md_link(filename, Path(filename))}")
    return "\n".join(lines) + "\n"


def build_quick_links_section(root_node: DirNode) -> str:
    lines = [f"## {EMOJI['link']} Quick Links\n"]

    root_files_lower = {f.lower(): f for f in root_node.files}
    candidates = [
        ("Main README", "readme.md"),
        ("Repository Index", None),  # handled separately (always exists once generated)
        ("License", "license.md"),
        ("License", "license"),
        ("Contributing", "contributing.md"),
    ]

    added_labels = set()
    any_link = False

    # Repository Index always resolvable (this very file), include it.
    lines.append(f"- {md_link('Repository Index', Path(INDEX_FILENAME))}")
    any_link = True

    for label, lower_name in candidates:
        if lower_name is None or label in added_labels:
            continue
        actual = root_files_lower.get(lower_name)
        if actual:
            lines.append(f"- {md_link(label, Path(actual))}")
            added_labels.add(label)
            any_link = True

    if not any_link:
        lines.append("_No additional quick links available._")

    return "\n".join(lines) + "\n"


def build_footer() -> str:
    return "---\n\nGenerated automatically by GitHub Actions.\n"


# --------------------------------------------------------------------------
# Rendering
# --------------------------------------------------------------------------

def render_index(root_node: DirNode, stats: RepoStats) -> str:
    parts = [
        build_header(),
        "",
        build_title(),
        "",
        build_toc(),
        "---\n",
        build_statistics_section(stats),
        "---\n",
        build_documentation_section(root_node),
        "---\n",
        build_tree_section(root_node),
        "---\n",
        build_root_files_section(root_node),
        "---\n",
        build_quick_links_section(root_node),
        build_footer(),
    ]
    return "\n".join(parts)


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------

def main() -> None:
    root = REPO_ROOT
    try:
        root_node = scan_repository(root)
    except Exception as exc:  # noqa: BLE001 - top-level safety net
        print(f"Error while scanning repository: {exc}")
        root_node = DirNode(name=root.name, rel_path=Path("."))

    try:
        stats = compute_stats(root, root_node)
    except Exception as exc:  # noqa: BLE001
        print(f"Error while computing statistics: {exc}")
        stats = RepoStats()

    content = render_index(root_node, stats)

    output_path = root / INDEX_FILENAME
    try:
        output_path.write_text(content, encoding="utf-8")
        print(f"Successfully generated {INDEX_FILENAME} at {output_path}")
    except (PermissionError, OSError) as exc:
        print(f"Failed to write {INDEX_FILENAME}: {exc}")
        raise


if __name__ == "__main__":
    main()
