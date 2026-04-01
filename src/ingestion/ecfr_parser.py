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


def parse_part_xml(
    xml_bytes: bytes,
    part_number: int,
    version_date: date,
) -> list[SectionRecord]:
    """
    Parse eCFR XML for a single CFR part into structured SectionRecord objects.

    Expected XML shape for 21 CFR Part 211:
        DIV5 TYPE="PART"     -> part
        DIV6 TYPE="SUBPART"  -> subpart
        DIV8 TYPE="SECTION"  -> section

    Args:
        xml_bytes: Raw XML bytes returned from the eCFR API
        part_number: Expected CFR part number, e.g. 211
        version_date: Date associated with the XML version

    Returns:
        A list of SectionRecord objects containing:
            - one part record
            - one record per subpart
            - one record per section

    Raises:
        ValueError: If the XML does not look like the requested part.
    """
    root = etree.fromstring(xml_bytes)
    records: list[SectionRecord] = []

    # The scoped API response for a single part is expected to have the part
    # itself as the root node.
    if root.tag != "DIV5" or root.attrib.get("TYPE") != "PART":
        raise ValueError(
            f"Expected root DIV5 TYPE=PART, got tag={root.tag}, attrs={dict(root.attrib)}"
        )

    root_part_number = root.attrib.get("N")
    if root_part_number != str(part_number):
        raise ValueError(
            f"Expected part {part_number}, got part {root_part_number}"
        )

    # ----------------------------
    # Part record
    # ----------------------------
    part_head = elem_text(root.find("HEAD")) or f"PART {part_number}"

    part_text_parts: list[str] = []
    if part_head:
        part_text_parts.append(part_head)

    # Keep top-level authority/source metadata in the part record.
    for child in root:
        if child.tag in {"AUTH", "SOURCE"}:
            text = elem_text(child)
            if text:
                part_text_parts.append(text)

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

    # ----------------------------
    # Subpart records
    # ----------------------------
    subpart_nodes = [
        child
        for child in root
        if child.tag == "DIV6" and child.attrib.get("TYPE") == "SUBPART"
    ]

    for subpart_node in subpart_nodes:
        subpart_letter = subpart_node.attrib.get("N", "")
        subpart_head = (
            elem_text(subpart_node.find("HEAD"))
            or f"Subpart {subpart_letter}".strip()
        )

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

        # ----------------------------
        # Section records inside subpart
        # ----------------------------
        section_nodes = [
            child
            for child in subpart_node
            if child.tag == "DIV8" and child.attrib.get("TYPE") == "SECTION"
        ]

        for section_node in section_nodes:
            section_number = section_node.attrib.get("N")
            if not section_number:
                continue

            section_head = elem_text(section_node.find("HEAD"))
            section_title = (
                strip_section_prefix(section_head, section_number)
                if section_head
                else None
            )
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