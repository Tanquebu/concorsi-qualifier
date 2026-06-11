import hashlib


def compute_hash(url: str, data_pubblicazione: str) -> str:
    """Restituisce SHA-256 hex di url + data_pubblicazione."""
    raw = f"{url}|{data_pubblicazione}"
    return hashlib.sha256(raw.encode()).hexdigest()
