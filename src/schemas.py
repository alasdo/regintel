from datetime import date
from typing import Literal

from pydantic import BaseModel


class ChangeClassification(BaseModel):
    change_type: Literal["substantive", "editorial", "structural"]
    severity: Literal["high", "medium", "low"]
    reason: str


class SectionRecord(BaseModel):
    section_number: str
    title: str | None = None
    level: int  # 0=part, 1=subpart, 2=section
    parent_section_number: str | None = None
    full_text: str
    version_date: date


class ImpactCitation(BaseModel):
    section_number: str
    relevance: str


AffectedFunction = Literal[
    "Quality Assurance",
    "Quality Control",
    "Production",
    "Validation",
    "Regulatory Affairs",
    "Engineering/Facilities",
    "Warehouse/Materials",
    "Documentation/Training",
]

AffectedProcess = Literal[
    "batch_record_review",
    "cleaning_validation",
    "process_validation",
    "equipment_qualification",
    "environmental_monitoring",
    "laboratory_testing",
    "stability_programme",
    "deviation_management",
    "capa_management",
    "change_control",
    "supplier_qualification",
    "data_integrity_controls",
    "training_programme",
    "document_control",
    "complaints_handling",
    "annual_product_review",
    "raw_material_testing",
    "packaging_labelling",
    "water_system_qualification",
    "hvac_qualification",
]


class ImpactAnalysisResult(BaseModel):
    summary: str
    what_changed: str
    affected_functions: list[AffectedFunction]
    affected_processes: list[AffectedProcess]
    recommended_action: Literal["immediate_review", "periodic_review", "awareness"]
    action_details: str
    confidence: Literal["high", "medium", "low"]
    citations: list[ImpactCitation]

class QACitation(BaseModel):
    section_number: str
    relevance: str


class QAResponse(BaseModel):
    answer: str
    citations: list[QACitation]
    confidence: Literal["high", "medium", "low"]