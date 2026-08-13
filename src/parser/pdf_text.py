import multiprocessing
import os
import resource
from pathlib import Path

# Memoria concessa al parsing di un singolo PDF, IN PIU' rispetto a quella che il processo
# padre già occupa (il figlio nasce da fork e ne eredita lo spazio di indirizzamento).
# Serve a trasformare un documento fuori scala in un errore recuperabile (MemoryError nel
# figlio → None) invece che in un SIGKILL dell'OOM killer, che ucciderebbe l'intero step e
# con lui il resto della pipeline. Riferimento: il PDF peggiore visto finora (scansione da
# 8,6 MB, 8 pagine) tocca i 365 MB. Override con PDF_PARSE_MEM_BUDGET_MB.
_MEM_BUDGET_MB = int(os.environ.get("PDF_PARSE_MEM_BUDGET_MB", "800"))
_PARSE_TIMEOUT_S = int(os.environ.get("PDF_PARSE_TIMEOUT_S", "600"))


def _address_space_bytes() -> int:
    """Spazio di indirizzamento attuale del processo, 0 se non leggibile."""
    try:
        with open("/proc/self/statm") as f:
            pages = int(f.read().split()[0])
        return pages * os.sysconf("SC_PAGE_SIZE")
    except Exception:
        return 0


def extract_text_pdf(file_path: Path) -> str | None:
    """Estrae testo da PDF con pdfplumber, fallback pypdf. Restituisce None se fallisce."""
    text = _run_isolated(_try_pdfplumber, file_path)
    if text:
        return text
    return _run_isolated(_try_pypdf, file_path)


def _run_isolated(func, file_path: Path) -> str | None:
    """Esegue func in un processo figlio con RLIMIT_AS. Restituisce None se il figlio muore."""
    try:
        ctx = multiprocessing.get_context("fork")
        recv, send = ctx.Pipe(duplex=False)
        proc = ctx.Process(target=_child, args=(func, file_path, send), daemon=True)
        proc.start()
        send.close()
    except Exception:
        # fork non disponibile: meglio parsare in-process che non parsare affatto
        return func(file_path)

    try:
        got = recv.poll(_PARSE_TIMEOUT_S)
        text = recv.recv() if got else None
    except EOFError:
        text = None  # il figlio è morto senza scrivere (MemoryError, SIGKILL, crash nativo)
    finally:
        recv.close()
        proc.join(timeout=5)
        if proc.is_alive():
            proc.kill()
            proc.join()

    return text


def _child(func, file_path: Path, send) -> None:
    limit = _address_space_bytes() + _MEM_BUDGET_MB * 1024 * 1024
    try:
        resource.setrlimit(resource.RLIMIT_AS, (limit, limit))
    except (ValueError, OSError):
        pass  # limite già più stretto dall'esterno: va bene comunque
    try:
        send.send(func(file_path))
    except Exception:
        try:
            send.send(None)
        except Exception:
            pass
    finally:
        send.close()
        # niente atexit/flush ereditati dal padre (connessione SQLite inclusa)
        os._exit(0)


def _try_pdfplumber(file_path: Path) -> str | None:
    try:
        import pdfplumber

        with pdfplumber.open(file_path) as pdf:
            parts = []
            for page in pdf.pages:
                parts.append(page.extract_text() or "")
                # pdfplumber tiene in cache gli oggetti di ogni pagina già visitata: su PDF
                # scansionati (immagini ad alta risoluzione) sono ~250 MB a pagina e senza
                # questo close() il consumo cresce fino all'OOM.
                page.close()
        text = "\n".join(parts).strip()
        return text if text else None
    except Exception:
        return None


def _try_pypdf(file_path: Path) -> str | None:
    try:
        from pypdf import PdfReader

        reader = PdfReader(str(file_path))
        parts = [page.extract_text() or "" for page in reader.pages]
        text = "\n".join(parts).strip()
        return text if text else None
    except Exception:
        return None
