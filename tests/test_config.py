from pathlib import Path

import yaml

from src.matcher.models import CandidatoProfilo

CONFIG_DIR = Path(__file__).parent.parent / "config"


def test_sources_yaml_loads() -> None:
    with open(CONFIG_DIR / "sources.yaml") as f:
        data = yaml.safe_load(f)
    assert "sources" in data
    sources = data["sources"]
    assert len(sources) >= 1
    for source in sources:
        assert "nome" in source
        assert "tipo" in source
        assert source["tipo"] in ("html", "pdf", "wordpress", "inpa_portal")
        assert "frequenza" in source
        if source["tipo"] not in ("inpa_portal",):
            assert "url" in source


def test_profilo_yaml_validates() -> None:
    with open(CONFIG_DIR / "profilo_candidato.yaml") as f:
        data = yaml.safe_load(f)
    profilo = CandidatoProfilo(**data)
    assert profilo.nome
    assert profilo.titolo_studio
