import warnings
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class Bando(BaseModel):
    id: str
    fonte: str
    url: str
    titolo: str
    ente: str
    categoria: str | None = None
    area_geografica: str | None = None
    posti: int | None = None
    scadenza: date | None = None
    titolo_studio_richiesto: str | None = None
    requisiti_formali: list[str] = Field(default_factory=list)
    materie_esame: list[str] = Field(default_factory=list)
    tassa_concorso: float | None = None
    link_candidatura: str | None = None
    documenti_richiesti: list[str] = Field(default_factory=list)
    testo_raw: str = ""
    parse_method: Literal["pdf_text", "pdf_ocr", "html", "parse_failed"]
    extraction_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    status: Literal["ok", "parse_failed", "expired", "duplicate"] = "ok"
    created_at: datetime = Field(default_factory=datetime.utcnow)

    @field_validator("scadenza", mode="before")
    @classmethod
    def warn_if_expired(cls, v: object) -> object:
        if isinstance(v, date) and v < date.today():
            warnings.warn(f"Bando con scadenza passata: {v}", stacklevel=2)
        return v
