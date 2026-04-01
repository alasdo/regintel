from datetime import date
from pydantic import BaseModel


class SectionRecord(BaseModel):
    section_number: str
    title: str | None = None
    level: int                   # 0=part, 1=subpart, 2=section
    parent_section_number: str | None = None
    full_text: str
    version_date: date