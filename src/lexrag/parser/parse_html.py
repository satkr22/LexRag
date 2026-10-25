from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from bs4 import BeautifulSoup, NavigableString, Tag  # type: ignore


ACT_DIRECTORIES: dict[str, str] = {
    "bns": "bns_sections",
    "bnss": "bnss_sections",
    "bsa": "bsa_sections",
    "constitution": "constitution_sections",
    "motor_vehicle": "motor_vehicle_sections",
}


@dataclass(frozen=True)
class Heading:
    """The heading that contains a provision."""

    number: str | None
    title: str | None
    range: str | None = None
    source: str = "unknown"

    def as_dict(self) -> dict[str, str | None]:
        return {
            "number": self.number,
            "title": self.title,
            "range": self.range,
        }


def clean_text(value: str | None) -> str:
    """Collapse formatting whitespace without changing legal wording."""

    return re.sub(r"\s+", " ", value or "").strip()


MOJIBAKE_MARKERS = ("â", "Â", "ð", "Ã", "�")


def mojibake_score(value: str) -> int:
    return sum(value.count(marker) for marker in MOJIBAKE_MARKERS)


def repair_mojibake(value: str) -> str:
    """Repair UTF-8 text that was decoded/encoded twice as Latin-1.

    The scraped files contain values such as ``â`` and ``Â·``.  A
    Latin-1-to-UTF-8 round trip converts those back to ``"`` and ``·``.  The
    score check prevents changing text when the conversion is not an
    improvement.
    """

    repaired = value
    for _ in range(2):
        before_score = mojibake_score(repaired)
        if before_score == 0:
            break
        try:
            candidate = repaired.encode("latin-1").decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            break
        if mojibake_score(candidate) >= before_score:
            break
        repaired = candidate
    return repaired.replace("�", "")


def natural_key(path: Path) -> list[int | str]:
    """Sort ``section-2.html`` before ``section-10.html``."""

    return [int(part) if part.isdigit() else part.lower() for part in re.split(r"(\d+)", path.name)]


def class_name(tag: Tag, expected: str) -> bool:
    """Return whether a BeautifulSoup tag has a particular CSS class."""

    return expected in (tag.get("class") or [])


def direct_text(tag: Tag | None) -> str:
    """Extract visible text while retaining punctuation and inline words."""

    return clean_text(tag.get_text(" ", strip=True) if tag else None)


BLOCK_TAGS = {
    "article",
    "div",
    "h1",
    "h2",
    "h3",
    "h4",
    "li",
    "p",
    "table",
    "tbody",
    "td",
    "tfoot",
    "th",
    "thead",
    "tr",
    "ul",
}


def article_content(article: Tag) -> str:
    """Extract article text without collapsing its newlines.

    The source has both pretty-printed and minified pages.  Existing source
    newlines are retained, and semantic block boundaries add a newline where
    minified markup would otherwise run paragraphs together.  Inline elements
    such as ``span`` and ``sup`` do not introduce artificial line breaks.
    """

    parts: list[str] = []

    def visit(node: Tag) -> None:
        for child in node.children:
            if isinstance(child, NavigableString):
                parts.append(str(child))
            elif isinstance(child, Tag):
                visit(child)
                if child.name in BLOCK_TAGS:
                    parts.append("\n")

    visit(article)
    return "".join(parts)


def _next_text(tag: Tag | None) -> str:
    """Return the first non-empty text node immediately after ``tag``."""

    if tag is None:
        return ""
    node = tag.next_sibling
    while isinstance(node, NavigableString):
        text = str(node).strip()
        if text:
            return clean_text(text)
        node = node.next_sibling
    return ""


def extract_article_number_and_title(
    article: Tag,
    fallback: str,
    preferred_title: str | None = None,
) -> tuple[str, str]:
    """Read an article's number and title from ``data-n``/``prov-title``.

    Most pages put the number in ``span.n``.  Schedule pages instead use
    ``<span class="n">Article</span>1`` where the label is in the span and the
    actual number is the following text node.
    """

    title_tag = article.find("h3", class_="prov-title")
    number = clean_text(article.get("data-n"))  # type: ignore
    number_tag = title_tag.find("span", class_="n") if title_tag else None
    number_text = direct_text(number_tag)

    if not number:
        if number_text and re.search(r"\d", number_text):
            # Normal case: span.n holds "12", "2A", "Article 12", etc.
            number = number_text
        else:
            # Schedule case: <span class="n">Article</span>1 — number is the
            # text node after the label span.
            match = re.match(r"^(\d+[A-Za-z]?)", _next_text(number_tag))
            if match:
                number = match.group(1)

    if not number:
        number = clean_text(fallback)
    number = number.rstrip(".")

    title = clean_text(preferred_title) or direct_text(title_tag)
    for prefix in (number_text, number):
        if prefix and title.startswith(prefix):
            title = title[len(prefix):].strip()

    return number, title


def extract_chip_title(article: Tag, article_number: str) -> str | None:
    """Use the clean navigation title when a group page provides one.

    A few Motor Vehicles headings contain amendment markers such as
    ``<sup>8</sup>[... ]``.  The corresponding chip title is the same legal
    heading without that editorial notation, so it is a better title value.
    """

    group = article.find_parent("section", class_="group")
    if not group:
        return None
    chip = group.find("a", class_="chip", attrs={"data-open": article_number})
    return clean_text(chip.get("title")) if chip and chip.get("title") else None  # type: ignore


def extract_group_heading(group: Tag) -> Heading:
    """Extract ``group-id``, ``h2``, and the optional range from one group."""

    group_head = group.find("div", class_="group-head")
    if not group_head:
        raise ValueError("A section.group has no div.group-head")

    number = direct_text(group_head.find("span", class_="group-id")) or None
    title = direct_text(group_head.find("h2")) or None
    range_text = direct_text(group_head.find("span", class_="group-range")) or None
    return Heading(number, title, range_text, source="group-head")


def load_manifest_headings(source_dir: Path) -> dict[str, Heading]:
    """Load heading metadata for one-provision pages from the scrape manifest."""

    manifest_path = source_dir / "_manifest.json"
    if not manifest_path.exists():
        return {}

    manifest = json.loads(repair_mojibake(manifest_path.read_text(encoding="utf-8")))
    headings: dict[str, Heading] = {}
    for group in manifest.get("groups", []):
        heading = Heading(
            clean_text(group.get("chapter")) or None,
            clean_text(group.get("title")) or None,
            clean_text(group.get("range")) or None,
            source="manifest",
        )
        for chip in group.get("chips", []):
            section = clean_text(str(chip.get("section", "")))
            if section:
                headings[section.casefold()] = heading
    return headings


def heading_from_page(article: Tag) -> Heading:
    """Infer a heading from the page-level citation on standalone pages."""

    citation = article.find_previous("p", class_="prov-cite")
    value = direct_text(citation)
    match = re.match(r"^(Chapter|Part)\s+([^·-]+?)\s*[·-]\s*(.+)$", value)
    if match:
        return Heading(
            f"{match.group(1)} {clean_text(match.group(2))}",
            clean_text(match.group(3)),
            None,
            source="page-citation",
        )
    return Heading(None, value or None, None, source="page-citation")


def document_title(soup: BeautifulSoup) -> str | None:
    """Get the act title when the page exposes an h1."""

    title = direct_text(soup.find("h1"))
    return title or None


def iter_page_articles(
    soup: BeautifulSoup,
    manifest_headings: dict[str, Heading],
    fallback_number: str = "",
    use_manifest: bool = True,
) -> Iterable[tuple[Tag, Heading, int]]:
    """Yield article, heading, and article position in source order."""

    groups = soup.find_all("section", class_="group")
    article_position = 0

    if groups:
        for group in groups:
            heading = extract_group_heading(group)
            reader = group.find("div", class_="reader")
            if not reader:
                continue
            for article in reader.find_all("article", class_="provision"):
                article_position += 1
                yield article, heading, article_position
        return

    # BSA section pages are standalone, but their manifest still contains the
    # same chapter/part heading metadata as group pages.
    for article in soup.find_all("article", class_="provision"):
        article_position += 1
        number, _ = extract_article_number_and_title(article, fallback_number)
        if use_manifest:
            heading = manifest_headings.get(number.casefold()) or heading_from_page(article)
        else:
            heading = heading_from_page(article)
        yield article, heading, article_position


def safe_section_stem(number: str, source_path: Path) -> str:
    """Create a stable output stem for numbers such as ``2A`` and schedules."""

    value = clean_text(number)
    if not value:
        value = source_path.stem.removeprefix("section-") or source_path.stem
    value = re.sub(r"[^A-Za-z0-9_-]+", "_", value)
    return f"section_{value}"


def safe_file_stem(source_path: Path) -> str:
    """Create a stable stem from the source filename."""

    value = re.sub(r"[^A-Za-z0-9_-]+", "_", source_path.stem).strip("_")
    return value or "file"


def parse_act(
    act: str,
    source_dir: Path,
    output_dir: Path,
    input_root: Path,
    clean_output: bool = False,
) -> list[dict[str, Any]]:
    """Parse all HTML files for one act and write one JSON file per article."""

    output_dir.mkdir(parents=True, exist_ok=True)
    if clean_output:
        for old_file in output_dir.glob("*.json"):
            if old_file.name == "manifest.json":
                continue
            old_file.unlink()

    manifest_headings = load_manifest_headings(source_dir)
    html_files = sorted(
        source_dir.glob("*.html"),
        key=lambda path: (path.stem.casefold() == "schedule", natural_key(path)),
    )
    records: list[dict[str, Any]] = []
    used_stems: dict[str, Path] = {}

    if "_sections" in act:
        act = act.replace("_sections", "")
    
    for source_order, source_path in enumerate(html_files, start=1):
        html = repair_mojibake(
            source_path.read_text(encoding="utf-8", errors="replace")
        )
        soup = BeautifulSoup(html, "html.parser")
        page_title = document_title(soup)

        fallback_number = source_path.stem.removeprefix("section-")
        use_manifest = not source_path.stem.casefold().startswith("schedule")

        for article, heading, article_order in iter_page_articles(
            soup,
            manifest_headings,
            fallback_number=fallback_number,
            use_manifest=use_manifest,
        ):
            article_number, article_title = extract_article_number_and_title(
                article, fallback_number
            )
            article_title = extract_chip_title(article, article_number) or article_title

            # Schedule articles use their filename as the stem so they can
            # never collide with a regular section of the same number
            # (e.g. Schedule Article 1 vs Section 1).
            if re.match(r"^schedule[-_]article[-_]", source_path.stem, re.IGNORECASE):
                stem = safe_file_stem(source_path)
            else:
                stem = safe_section_stem(article_number, source_path)

            if stem in used_stems:
                previous = used_stems[stem]
                raise ValueError(
                    f"Duplicate output {stem!r} for {source_path} and {previous}; "
                    "article numbers must be unique within an act."
                )
            used_stems[stem] = source_path

            relative_source = source_path.relative_to(input_root).as_posix()
            record: dict[str, Any] = {
                "metadata": {
                    "act": act,
                    "document_title": page_title,
                    "source_file": relative_source,
                    "source_order": source_order,
                    "article_order": article_order,
                    "order": len(records) + 1,
                    "stem": stem,
                    "heading_number": heading.number,
                    "heading_title": heading.title,
                    "heading_range": heading.range,
                    "heading_source": heading.source,
                    "article_number": article_number,
                    "article_title": article_title,
                },
                "id": f'{act}_{stem}',
                "heading": heading.as_dict(),
                "article": {
                    "number": article_number,
                    "title": article_title,
                    "content": article_content(article),
                    "html": str(article),
                    "inner_html": "".join(str(child) for child in article.children),
                },
            }
            output_path = output_dir / f"{stem}.json"
            output_path.write_text(
                json.dumps(record, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            records.append(record)

    index = {
        "act": act,
        "source_directory": source_dir.as_posix(),
        "output_directory": output_dir.as_posix(),
        "count": len(records),
        "files": [
            {
                "order": record["metadata"]["order"],
                "article_number": record["metadata"]["article_number"],
                "article_title": record["metadata"]["article_title"],
                "file": f"{record['metadata']['stem']}.json",
            }
            for record in records
        ],
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(index, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return records


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input-root",
        type=Path,
        default=Path("src/lexrag/scrapped"),
        help="Directory containing *_sections directories.",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path("src/lexrag/parsed"),
        help="Directory in which act output directories are created.",
    )
    parser.add_argument(
        "--acts",
        nargs="+",
        choices=sorted(ACT_DIRECTORIES),
        default=sorted(ACT_DIRECTORIES),
        help="Acts to parse (default: all supported acts).",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Remove generated section JSON files before parsing each act.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    total = 0
    dirs = [p.name for p in Path(args.input_root).iterdir() if p.is_dir()]

    for act in dirs:
        source_dir = args.input_root / act
        output_dir = args.output_root / act
        if not source_dir.exists():
            raise FileNotFoundError(f"Input directory does not exist: {source_dir}")
        records = parse_act(
            act,
            source_dir,
            output_dir,
            args.input_root,
            clean_output=args.clean,
        )
        total += len(records)
        print(f"{act}: wrote {len(records)} section files to {output_dir}")
    print(f"Total: wrote {total} section files")


if __name__ == "__main__":
    main()


# run with: 

# python src/lexrag/parser/parse_html.py --clean

# or

# python src/lexrag/parser/parse_scrapped_html.py \
#     --input-root src/lexrag/scrapped \
#     --output-root src/lexrag/parsed