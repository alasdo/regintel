from datetime import date
from pathlib import Path
from lxml import etree

from src.ingestion.ecfr_client import fetch_part_xml


def main():
    as_of = date(2026, 3, 30)
    xml_bytes = fetch_part_xml(title=21, part=211, as_of_date=as_of)

    output_dir = Path("data")
    output_dir.mkdir(exist_ok=True)

    raw_file = output_dir / "part_211_raw.xml"
    pretty_file = output_dir / "part_211_pretty.xml"

    raw_file.write_bytes(xml_bytes)

    root = etree.fromstring(xml_bytes)
    pretty_xml = etree.tostring(
        root,
        pretty_print=True,
        encoding="utf-8",
        xml_declaration=True,
    )
    pretty_file.write_bytes(pretty_xml)

    print(f"Saved raw XML to: {raw_file}")
    print(f"Saved pretty XML to: {pretty_file}")
    print(f"Root tag: {root.tag}")
    print(f"Root attrs: {dict(root.attrib)}")


if __name__ == "__main__":
    main()