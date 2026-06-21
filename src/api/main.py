import datetime
import os
import sqlite3
import sys
import uuid
from pathlib import Path

import src.env  # noqa: F401
from fastapi import Depends, FastAPI, HTTPException
from fastapi.security import APIKeyHeader
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from src.reporter import reprocess_bando

_DB_PATH = Path("concorsi.db")

_API_KEY = os.environ.get("API_KEY", "")
if not _API_KEY:
    print("ERRORE: variabile API_KEY non impostata nel .env", file=sys.stderr)
    sys.exit(1)

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=True)

app = FastAPI(title="concorsi-qualifier API", docs_url=None, redoc_url=None)


async def _verify_key(api_key: str = Depends(_api_key_header)) -> None:
    if api_key != _API_KEY:
        raise HTTPException(status_code=403, detail="API key non valida")


class RetryRequest(BaseModel):
    bando_id: str


class RetryResponse(BaseModel):
    ok: bool
    spiegazione: str
    azioni_consigliate: list[str]


@app.post("/api/reporter/retry", dependencies=[Depends(_verify_key)])
async def retry_reporter(body: RetryRequest) -> RetryResponse:
    try:
        result = await run_in_threadpool(reprocess_bando, body.bando_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    return RetryResponse(
        ok=True,
        spiegazione=str(result.get("spiegazione", "")),
        azioni_consigliate=list(result.get("azioni_consigliate", [])),  # type: ignore[arg-type]
    )


class ScartaRequest(BaseModel):
    bando_id: str


def _do_scarta(bando_id: str) -> None:
    if not _DB_PATH.exists():
        raise ValueError(f"DB non trovato: {_DB_PATH}")
    with sqlite3.connect(_DB_PATH) as conn:
        row = conn.execute("SELECT id FROM bandi WHERE id = ?", (bando_id,)).fetchone()
        if row is None:
            raise ValueError(f"Bando non trovato: {bando_id}")
        conn.execute("UPDATE bandi SET status = 'scartato' WHERE id = ?", (bando_id,))
        conn.execute(
            "INSERT INTO user_actions (id, bando_id, action, created_at) VALUES (?, ?, ?, ?)",
            (str(uuid.uuid4()), bando_id, "scartato", datetime.datetime.utcnow().isoformat()),
        )


@app.post("/api/bandi/scarta", dependencies=[Depends(_verify_key)])
async def scarta_bando(body: ScartaRequest) -> dict[str, bool]:
    try:
        await run_in_threadpool(_do_scarta, body.bando_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    return {"ok": True}


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
