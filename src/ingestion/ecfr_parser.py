from __future__ import annotations

from datetime import date

from lxml import etree

from src.schemas import SectionRecord


def clean_text(text: str | None) -> str:
    """Normalize whitespace and return a stripped string."""
    if not text:
        return ""
    return " ".join(text.split()).strip()


def elem_text(elem: etree._Element | None) -> str | None:
    """Extract normalized text from an XML element, or None if empty."""
    if elem is None:
        return None
    text = clean_text(" ".join(elem.itertext()))
    return text or None


def strip_section_prefix(head_text: str, section_number: str) -> str:
    """
    Remove the leading '§ 211.1' style prefix from a section heading.

    Example:
        '§ 211.1 Scope.' -> 'Scope.'
    """
    head_text = clean_text(head_text)
    prefix = f"§ {section_number}"
    if head_text.startswith(prefix):
        return head_text[len(prefix):].strip()
    return head_text


def build_section_full_text(
    section_node: etree._Element,
    section_head: str | None,
) -> str:
    """
    Build section text from the section heading plus child content.

    V1 intentionally keeps subsection markers like (a), (1), (i) inside the
    section text rather than splitting them into separate records.
    """
    parts: list[str] = []

    if section_head:
        parts.append(clean_text(section_head))

    for child in section_node:
        if child.tag == "P":
            text = elem_text(child)
            if text:
                parts.append(text)
        elif child.tag == "CITA":
            text = elem_text(child)
            if text:
                parts.append(text)

    return "\n".join(parts).strip()


def parse_part_xml(xml_bytes: bytes, part_number: int, version_date: date) -> list[SectionRecord]:
    root = etree.fromstring(xml_bytes)
    records: list[SectionRecord] = []

    if root.tag != "DIV5" or root.attrib.get("TYPE") != "PART":
        raise ValueError(f"Expected root DIV5 TYPE=PART, got tag={root.tag}, attrs={dict(root.attrib)}")

    root_n = root.attrib.get("N")
    if root_n != str(part_number):
        raise ValueError(f"Expected part {part_number}, got part {root_n}")

    part_head = elem_text(root.find("HEAD")) or f"PART {part_number}"

    # Part record
    part_text_parts = []
    if part_head:
        part_text_parts.append(part_head)

    for child in root:
        if child.tag in {"AUTH", "SOURCE"}:
            txt = elem_text(child)
            if txt:
                part_text_parts.append(txt)

    records.append(
        SectionRecord(
            section_number=str(part_number),
            title=part_head,
            level=0,
            parent_section_number=None,
            full_text="\n".join(part_text_parts).strip(),
            version_date=version_date,
        )
    )

    # Case 1: subparts exist (like Part 211)
    subpart_nodes = [
        child for child in root
        if child.tag == "DIV6" and child.attrib.get("TYPE") == "SUBPART"
    ]

    if subpart_nodes:
        for subpart_node in subpart_nodes:
            subpart_head = elem_text(subpart_node.find("HEAD")) or f"Subpart {subpart_node.attrib.get('N', '')}".strip()

            records.append(
                SectionRecord(
                    section_number=subpart_head,
                    title=subpart_head,
                    level=1,
                    parent_section_number=str(part_number),
                    full_text=subpart_head,
                    version_date=version_date,
                )
            )

            section_nodes = [
                child for child in subpart_node
                if child.tag == "DIV8" and child.attrib.get("TYPE") == "SECTION"
            ]

            for section_node in section_nodes:
                section_number = section_node.attrib.get("N")
                if not section_number:
                    continue

                section_head = elem_text(section_node.find("HEAD"))
                section_title = strip_section_prefix(section_head, section_number) if section_head else None
                section_full_text = build_section_full_text(section_node, section_head)

                if not section_full_text:
                    continue

                records.append(
                    SectionRecord(
                        section_number=section_number,
                        title=section_title,
                        level=2,
                        parent_section_number=subpart_head,
                        full_text=section_full_text,
                        version_date=version_date,
                    )
                )

        return records

    # Case 2: direct sections under part (like Part 210)
    direct_section_nodes = [
        child for child in root
        if child.tag == "DIV8" and child.attrib.get("TYPE") == "SECTION"
    ]

    for section_node in direct_section_nodes:
        section_number = section_node.attrib.get("N")
        if not section_number:
            continue

        section_head = elem_text(section_node.find("HEAD"))
        section_title = strip_section_prefix(section_head, section_number) if section_head else None
        section_full_text = build_section_full_text(section_node, section_head)

        if not section_full_text:
            continue

        records.append(
            SectionRecord(
                section_number=section_number,
                title=section_title,
                level=2,
                parent_section_number=str(part_number),
                full_text=section_full_text,
                version_date=version_date,
            )
        )

    return records