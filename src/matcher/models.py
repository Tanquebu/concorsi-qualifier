import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

DISCLAIMER = (
    "Analisi assistita. La verifica finale dei requisiti formali "
    "resta responsabilità del candidato."
)


class CandidatoProfilo(BaseModel):
    nome: str
    titolo_studio: str
    aree_preferite: list[str] = Field(default_factory=list)
    settori: list[str] = Field(default_factory=list)
    anni_esperienza: int | None = None
    parole_chiave: list[str] = Field(default_factory=list)
    esclusioni: list[str] = Field(default_factory=list)


class CheckItem(BaseModel):
    requisito: str
    esito: Literal["ok", "warning", "fail", "unknown"]
    nota: str | None = None


class MatchResult(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    bando_id: str
    profilo_nome: str
    compatibilita: Literal["alta", "media", "bassa", "da_verificare"]
    checklist: list[CheckItem]
    da_verificare: list[str] = Field(default_factory=list)
    spiegazione: str = ""
    disclaimer: str = DISCLAIMER
    created_at: datetime = Field(default_factory=datetime.utcnow)
