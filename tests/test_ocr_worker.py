import sqlite3
from unittest.mock import Mock

import pytest

import ocr_worker as worker


@pytest.fixture
def queues(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(worker, '_DB', tmp_path / 'concorsi.db')
    monkeypatch.setattr(worker, '_QUEUE', tmp_path / 'queue.txt')
    monkeypatch.setattr(worker, '_DEFERRED_QUEUE', tmp_path / 'waiting.txt')
    with sqlite3.connect(worker._DB) as conn:
        conn.execute('CREATE TABLE bandi (id TEXT PRIMARY KEY, url TEXT, fonte TEXT)')
        conn.execute("INSERT INTO bandi VALUES ('valid', 'url', 'fonte')")
    return tmp_path


def test_missing_record_never_runs_ocr(queues, monkeypatch):
    ocr = Mock(side_effect=AssertionError('OCR non deve partire'))
    monkeypatch.setattr(worker, 'extract_text_ocr', ocr)
    assert worker.process_one('missing') == (False, 'bando non in DB')
    ocr.assert_not_called()


def test_defer_and_restore_without_duplicates(queues):
    worker._QUEUE.write_text('valid\nmissing\nmissing\n')
    assert worker.reconcile_queue() == (1, 1)
    assert worker._QUEUE.read_text() == 'valid\n'
    assert worker._DEFERRED_QUEUE.read_text() == 'missing\n'
    assert worker.reconcile_queue() == (1, 1)
    with sqlite3.connect(worker._DB) as conn:
        conn.execute("INSERT INTO bandi VALUES ('missing', 'url', 'fonte')")
    assert worker.reconcile_queue() == (2, 0)
    assert worker._QUEUE.read_text() == 'valid\nmissing\n'
    assert worker._DEFERRED_QUEUE.read_text() == ''


def test_db_failure_preserves_queues(queues):
    worker._QUEUE.write_text('valid\n')
    worker._DEFERRED_QUEUE.write_text('missing\n')
    worker._DB.unlink()
    with pytest.raises(sqlite3.OperationalError):
        worker.reconcile_queue()
    assert worker._QUEUE.read_text() == 'valid\n'
    assert worker._DEFERRED_QUEUE.read_text() == 'missing\n'
    assert not worker._DB.exists()


def test_valid_record_still_extracts(queues, monkeypatch):
    raw = queues / 'data' / 'raw'
    raw.mkdir(parents=True)
    (raw / 'valid.allegato.pdf').write_bytes(b'pdf')
    (raw / 'valid.html').write_text('<p>Bando</p>')
    monkeypatch.setattr(worker, 'extract_text_ocr', Mock(return_value='Testo OCR'))
    extract = Mock()
    monkeypatch.setattr(worker, 'extract', extract)
    assert worker.process_one('valid')[0] is True
    assert 'Testo OCR' in extract.call_args.args[0]
    assert extract.call_args.kwargs['bando_id'] == 'valid'
