"""tikz_extract.py - Unpack e-print archives and parse TikZ environments out of LaTeX."""

import gzip
import os
import re
import shutil
import tarfile
import tempfile
from typing import Optional

from tikz_models import TikzFigure, TIKZ_ENVIRONMENTS, TIKZ_TYPE_MAP


def processArchive(arxiv_id: str, content: bytes) -> list[TikzFigure]:
    """Process downloaded archive content and extract TikZ figures.

    Tries tar.gz first, falls back to single-file gzip.
    """
    tmp_dir = tempfile.mkdtemp(prefix="arxiv_tikz_")
    try:
        tex_files = extractArchive(content, tmp_dir)
        if not tex_files:
            return []

        # Pass 1: collect all \usetikzlibrary{} across all files
        libraries_used = collectLibraries(tex_files)

        # Pass 2: extract TikZ environments from each file
        figures = []
        figure_index = 0
        for tex_path in tex_files:
            tex_content = readTexFile(tex_path)
            if not tex_content:
                continue

            source_name = os.path.relpath(tex_path, tmp_dir)
            extracted = extractTikzFromContent(
                tex_content, arxiv_id, source_name, libraries_used, figure_index
            )
            figures.extend(extracted)
            figure_index += len(extracted)

        return figures
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def extractArchive(content: bytes, tmp_dir: str) -> list[str]:
    """Extract archive to tmp_dir and return list of .tex file paths.

    Tries tar.gz first, then single-file gzip.
    """
    # Try tar.gz
    try:
        import io
        with tarfile.open(fileobj=io.BytesIO(content), mode="r:gz") as tar:
            tar.extractall(tmp_dir, filter="data")
        return findTexFiles(tmp_dir)
    except (tarfile.TarError, gzip.BadGzipFile, EOFError):
        pass

    # Try plain tar (some e-prints are uncompressed tar)
    try:
        import io
        with tarfile.open(fileobj=io.BytesIO(content), mode="r:") as tar:
            tar.extractall(tmp_dir, filter="data")
        return findTexFiles(tmp_dir)
    except (tarfile.TarError, EOFError):
        pass

    # Try single-file gzip
    try:
        decompressed = gzip.decompress(content)
        tex_path = os.path.join(tmp_dir, "main.tex")
        with open(tex_path, "wb") as f:
            f.write(decompressed)
        return [tex_path]
    except (gzip.BadGzipFile, EOFError):
        pass

    # Try raw .tex (some papers are just plain LaTeX)
    try:
        text = content.decode("utf-8", errors="ignore")
        if "\\begin{document}" in text or "\\documentclass" in text:
            tex_path = os.path.join(tmp_dir, "main.tex")
            with open(tex_path, "w", encoding="utf-8") as f:
                f.write(text)
            return [tex_path]
    except Exception:
        pass

    return []


def findTexFiles(directory: str) -> list[str]:
    """Recursively find all .tex files in directory."""
    tex_files = []
    for root, _dirs, files in os.walk(directory):
        for name in sorted(files):
            if name.endswith(".tex"):
                tex_files.append(os.path.join(root, name))
    return tex_files


def readTexFile(path: str) -> Optional[str]:
    """Read a .tex file, trying common encodings."""
    for encoding in ["utf-8", "latin-1"]:
        try:
            with open(path, "r", encoding=encoding) as f:
                return f.read()
        except (UnicodeDecodeError, OSError):
            continue
    return None


def collectLibraries(tex_files: list[str]) -> list[str]:
    """Collect all \\usetikzlibrary{} declarations across all .tex files."""
    libraries = set()
    pattern = re.compile(r"\\usetikzlibrary\{([^}]+)\}")

    for path in tex_files:
        content = readTexFile(path)
        if not content:
            continue
        for match in pattern.finditer(content):
            for lib in match.group(1).split(","):
                lib = lib.strip()
                if lib:
                    libraries.add(lib)

    return sorted(libraries)


def extractTikzFromContent(
    content: str,
    id_arxiv: str,
    source_file: str,
    libraries_used: list[str],
    start_index: int,
) -> list[TikzFigure]:
    """Extract TikZ environments from a single .tex file content.

    Uses a counting parser to handle nested \\begin/\\end correctly.
    """
    figures = []
    figure_index = start_index

    for env_name in TIKZ_ENVIRONMENTS:
        begin_tag = f"\\begin{{{env_name}}}"
        pos = 0

        while True:
            start = content.find(begin_tag, pos)
            if start == -1:
                break

            # Use counting parser for balanced begin/end
            tikz_code = extractBalancedEnvironment(content, start, env_name)
            if tikz_code is None:
                pos = start + len(begin_tag)
                continue

            # Skip if this is nested inside an already-matched tikzpicture
            # (e.g. \begin{axis} inside \begin{tikzpicture})
            if env_name == "axis" and isNestedInTikzpicture(content, start):
                pos = start + len(tikz_code)
                continue

            # Extract caption and label from surrounding figure environment
            caption = extractCaption(content, start)
            label = extractLabel(content, start)

            figures.append(TikzFigure(
                id_arxiv=id_arxiv,
                figure_index=figure_index,
                tikz_type=TIKZ_TYPE_MAP.get(env_name, env_name),
                tikz_code=tikz_code,
                source_file=source_file,
                libraries_used=libraries_used,
                caption=caption,
                label=label,
            ))
            figure_index += 1
            pos = start + len(tikz_code)

    return figures


def extractBalancedEnvironment(
    content: str, start: int, env_name: str
) -> Optional[str]:
    """Extract a balanced \\begin{env}...\\end{env} block using depth counting.

    Handles nested environments of the same type correctly.
    """
    begin_tag = f"\\begin{{{env_name}}}"
    end_tag = f"\\end{{{env_name}}}"
    depth = 0
    pos = start

    while pos < len(content):
        next_begin = content.find(begin_tag, pos if depth > 0 else pos + 1)
        next_end = content.find(end_tag, pos)

        if next_end == -1:
            # Unbalanced: no closing tag found
            return None

        if next_begin != -1 and next_begin < next_end:
            # Found a nested begin before the next end
            depth += 1
            pos = next_begin + len(begin_tag)
        else:
            # Found an end tag
            if depth == 0:
                end_pos = next_end + len(end_tag)
                return content[start:end_pos]
            else:
                depth -= 1
                pos = next_end + len(end_tag)

    return None


def isNestedInTikzpicture(content: str, pos: int) -> bool:
    """Check if position is inside a \\begin{tikzpicture} block."""
    # Look backwards for the nearest tikzpicture begin/end
    before = content[:pos]
    last_begin = before.rfind("\\begin{tikzpicture}")
    last_end = before.rfind("\\end{tikzpicture}")

    if last_begin == -1:
        return False

    # If the last tikzpicture begin is after the last tikzpicture end,
    # we are inside a tikzpicture
    return last_begin > last_end


def extractCaption(content: str, tikz_start: int) -> Optional[str]:
    """Extract \\caption{} from surrounding \\begin{figure} environment."""
    # Look backwards for \begin{figure}
    search_start = max(0, tikz_start - 500)
    before = content[search_start:tikz_start]

    fig_begin = before.rfind("\\begin{figure}")
    if fig_begin == -1:
        return None

    # Find the end of this figure environment
    fig_abs_start = search_start + fig_begin
    fig_end = content.find("\\end{figure}", tikz_start)
    if fig_end == -1:
        return None

    figure_block = content[fig_abs_start:fig_end + len("\\end{figure}")]

    # Extract caption using balanced braces
    caption_match = re.search(r"\\caption\{", figure_block)
    if not caption_match:
        return None

    caption_start = caption_match.end()
    depth = 1
    i = caption_start
    while i < len(figure_block) and depth > 0:
        if figure_block[i] == "{":
            depth += 1
        elif figure_block[i] == "}":
            depth -= 1
        i += 1

    if depth == 0:
        caption_text = figure_block[caption_start:i - 1]
        # Clean up the caption text
        caption_text = re.sub(r"\\label\{[^}]*\}", "", caption_text)
        caption_text = " ".join(caption_text.split()).strip()
        return caption_text if caption_text else None

    return None


def extractLabel(content: str, tikz_start: int) -> Optional[str]:
    """Extract \\label{} from surrounding \\begin{figure} environment."""
    search_start = max(0, tikz_start - 500)
    before = content[search_start:tikz_start]

    fig_begin = before.rfind("\\begin{figure}")
    if fig_begin == -1:
        return None

    fig_abs_start = search_start + fig_begin
    fig_end = content.find("\\end{figure}", tikz_start)
    if fig_end == -1:
        return None

    figure_block = content[fig_abs_start:fig_end + len("\\end{figure}")]

    label_match = re.search(r"\\label\{([^}]+)\}", figure_block)
    if label_match:
        return label_match.group(1)

    return None
