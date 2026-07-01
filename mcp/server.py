import asyncio
import json
import sys
from pathlib import Path

# Aggiunge la project root al path prima di qualsiasi import locale
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

import tools  # noqa: E402, I001
from mcp import types  # noqa: E402
from mcp.server import Server  # noqa: E402
from mcp.server.stdio import stdio_server  # noqa: E402

app = Server("concorsi")


@app.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="get_bandi",
            description=(
                "Lista bandi dal database SQLite, ordinati per scadenza. "
                "Esclude il testo grezzo. Se compatibilita è specificato, "
                "restituisce solo i bandi che hanno già un match result con quel valore."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "compatibilita": {
                        "type": "string",
                        "enum": ["alta", "media", "bassa", "da_verificare"],
                        "description": (
                            "Filtra per compatibilità esatta (richiede matcher già eseguito)"
                        ),
                    },
                    "scadenza_entro_giorni": {
                        "type": "integer",
                        "description": "Solo bandi con scadenza entro N giorni da oggi",
                    },
                    "limit": {
                        "type": "integer",
                        "default": 20,
                        "description": "Numero massimo di risultati (default 20)",
                    },
                },
            },
        ),
        types.Tool(
            name="get_match_results",
            description=(
                "Risultati di matching bando↔profilo con checklist e punti da verificare. "
                "Filtrabile per compatibilità minima (alta include solo alta; "
                "media include alta+media) e/o per ID bando specifico."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "compatibilita_minima": {
                        "type": "string",
                        "enum": ["alta", "media", "bassa", "da_verificare"],
                        "description": "Compatibilità minima: 'alta'→solo alta; 'media'→alta+media",
                    },
                    "bando_id": {
                        "type": "string",
                        "description": "Filtra per ID bando specifico",
                    },
                    "limit": {
                        "type": "integer",
                        "default": 20,
                        "description": "Numero massimo di risultati (default 20)",
                    },
                },
            },
        ),
        types.Tool(
            name="get_collector_runs",
            description=(
                "Storico delle run del collector: quante volte è stato eseguito, "
                "quanti bandi trovati/nuovi/duplicati, eventuali errori."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "default": 10,
                        "description": "Ultime N run (default 10)",
                    },
                },
            },
        ),
        types.Tool(
            name="search_bando",
            description=(
                "Cerca bandi per titolo o ente (LIKE case-insensitive). "
                "Restituisce id, titolo, ente, area, scadenza, status di sistema, "
                "user_status (applicato/da_valutare/null) e compatibilità. "
                "Utile per trovare un bando specifico di cui si conosce solo parte del nome."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Testo da cercare in titolo o ente",
                    },
                    "limit": {
                        "type": "integer",
                        "default": 10,
                        "description": "Numero massimo di risultati (default 10)",
                    },
                },
                "required": ["query"],
            },
        ),
        types.Tool(
            name="get_bando",
            description=(
                "Dettaglio completo di un singolo bando dato il suo ID (hash SHA256). "
                "Include tutti i campi estratti, user_status, e il match result completo "
                "con checklist, da_verificare e spiegazione AI."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "id": {
                        "type": "string",
                        "description": "ID del bando (hash SHA256, 64 caratteri hex)",
                    },
                },
                "required": ["id"],
            },
        ),
        types.Tool(
            name="trigger_pipeline",
            description=(
                "Lancia un modulo della pipeline come subprocess. "
                "Aspetta 10 secondi: moduli veloci (matcher, notifier) "
                "restituiscono output completo; moduli lenti (collector, extractor, reporter) "
                "avviano in background e restituiscono PID + path log file."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "module": {
                        "type": "string",
                        "enum": ["collector", "extractor", "matcher", "reporter", "notifier"],
                        "description": "Modulo da eseguire",
                    },
                    "extra_args": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Argomenti CLI aggiuntivi (es. ['--force'])",
                    },
                },
                "required": ["module"],
            },
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    if name == "search_bando":
        result = tools.search_bando(
            query=arguments["query"],
            limit=arguments.get("limit", 10),
        )
    elif name == "get_bando":
        result = tools.get_bando(id=arguments["id"])
    elif name == "get_bandi":
        result = tools.get_bandi(
            compatibilita=arguments.get("compatibilita"),
            scadenza_entro_giorni=arguments.get("scadenza_entro_giorni"),
            limit=arguments.get("limit", 20),
        )
    elif name == "get_match_results":
        result = tools.get_match_results(
            compatibilita_minima=arguments.get("compatibilita_minima"),
            bando_id=arguments.get("bando_id"),
            limit=arguments.get("limit", 20),
        )
    elif name == "get_collector_runs":
        result = tools.get_collector_runs(limit=arguments.get("limit", 10))
    elif name == "trigger_pipeline":
        result = await tools.trigger_pipeline(
            module=arguments["module"],
            extra_args=arguments.get("extra_args"),
        )
    else:
        result = {"error": f"Tool sconosciuto: {name!r}"}

    return [types.TextContent(type="text", text=json.dumps(result, ensure_ascii=False, indent=2))]


async def main() -> None:
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
