from datetime import date, timedelta
from unittest.mock import MagicMock, patch

import httpx

from src.extractor.models import Bando
from src.matcher.models import CheckItem, MatchResult
from src.notifier import filter_bandi, send_digest
from src.notifier.digest import build_digest_payload


def _bando(**kwargs: object) -> Bando:
    defaults: dict[str, object] = {
        "id": "b001",
        "fonte": "inpa",
        "url": "https://example.com/bando/1",
        "titolo": "Concorso Informatici",
        "ente": "Comune di Roma",
        "parse_method": "pdf_text",
        "scadenza": date.today() + timedelta(days=15),
    }
    defaults.update(kwargs)
    return Bando(**defaults)  # type: ignore[arg-type]


def _match(**kwargs: object) -> MatchResult:
    defaults: dict[str, object] = {
        "bando_id": "b001",
        "profilo_nome": "Mario Rossi",
        "compatibilita": "alta",
        "checklist": [CheckItem(requisito="Titolo di studio", esito="ok")],
    }
    defaults.update(kwargs)
    return MatchResult(**defaults)  # type: ignore[arg-type]


# --- filter_bandi ---

def test_filter_keeps_alta() -> None:
    results = [(_bando(), _match(compatibilita="alta"))]
    assert len(filter_bandi(results)) == 1


def test_filter_keeps_media() -> None:
    results = [(_bando(), _match(compatibilita="media"))]
    assert len(filter_bandi(results)) == 1


def test_filter_excludes_bassa() -> None:
    results = [(_bando(), _match(compatibilita="bassa"))]
    assert filter_bandi(results) == []


def test_filter_excludes_da_verificare() -> None:
    results = [(_bando(), _match(compatibilita="da_verificare"))]
    assert filter_bandi(results) == []


def test_filter_excludes_expired() -> None:
    bando = _bando(scadenza=date(2020, 1, 1))
    results = [(bando, _match())]
    assert filter_bandi(results) == []


def test_filter_excludes_beyond_days_ahead() -> None:
    bando = _bando(scadenza=date.today() + timedelta(days=60))
    results = [(bando, _match())]
    assert filter_bandi(results, days_ahead=30) == []


def test_filter_empty_list() -> None:
    assert filter_bandi([]) == []


def test_filter_excludes_none_scadenza() -> None:
    bando = _bando(scadenza=None)
    results = [(bando, _match())]
    assert filter_bandi(results) == []


# --- build_digest_payload ---

def test_build_payload_structure() -> None:
    bando = _bando()
    match = _match()
    payload = build_digest_payload([(bando, match)])
    assert "html" in payload
    assert "plain_text" in payload
    assert "bandi" in payload


def test_build_payload_empty() -> None:
    payload = build_digest_payload([])
    assert payload["bandi"] == []
    assert payload["html"] == ""
    assert payload["plain_text"] == ""


def test_build_payload_content() -> None:
    bando = _bando(titolo="Concorso Test", ente="Ente Test")
    payload = build_digest_payload([(bando, _match())])
    html = str(payload["html"])
    plain = str(payload["plain_text"])
    assert "Concorso Test" in html
    assert "Concorso Test" in plain
    assert "ALTA" in html or "alta" in html


# --- send_digest ---

def test_send_digest_calls_webhook() -> None:
    bando = _bando()
    match = _match()
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None

    with (
        patch("src.notifier.httpx.post", return_value=mock_response) as mock_post,
        patch.dict("os.environ", {"NOTIFIER_WEBHOOK_URL": "https://hook.example.com"}),
    ):
        send_digest([(bando, match)])

    mock_post.assert_called_once()
    _, kwargs = mock_post.call_args
    assert "json" in kwargs
    assert "bandi" in kwargs["json"]


def test_send_digest_webhook_down() -> None:
    bando = _bando()
    match = _match()

    with (
        patch("src.notifier.httpx.post", side_effect=httpx.ConnectError("down")),
        patch.dict("os.environ", {"NOTIFIER_WEBHOOK_URL": "https://hook.example.com"}),
    ):
        send_digest([(bando, match)])  # nessuna eccezione propagata


def test_send_digest_empty() -> None:
    with (
        patch("src.notifier.httpx.post") as mock_post,
        patch.dict("os.environ", {"NOTIFIER_WEBHOOK_URL": "https://hook.example.com"}),
    ):
        send_digest([])

    mock_post.assert_not_called()


def test_send_digest_no_webhook_url() -> None:
    bando = _bando()
    match = _match()

    with (
        patch("src.notifier.httpx.post") as mock_post,
        patch.dict("os.environ", {}, clear=True),
    ):
        send_digest([(bando, match)])

    mock_post.assert_not_called()
