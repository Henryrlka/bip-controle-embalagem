from datetime import date, datetime

import pytest

from bip.db import Repo
from bip.relatorios import periodo


def test_periodo_dia():
    assert periodo("dia", date(2026, 10, 21)) == (datetime(2026, 10, 21), datetime(2026, 10, 22))


def test_semana_no_domingo():
    assert periodo("semana", date(2026, 10, 25)) == (datetime(2026, 10, 19), datetime(2026, 10, 26))


def test_semana_na_segunda():
    assert periodo("semana", date(2026, 10, 19)) == (datetime(2026, 10, 19), datetime(2026, 10, 26))


def test_periodo_mes_dezembro():
    assert periodo("mes", date(2026, 12, 5)) == (datetime(2026, 12, 1), datetime(2027, 1, 1))


def test_periodo_invalido():
    with pytest.raises(ValueError):
        periodo("ano", date(2026, 10, 21))


@pytest.fixture
def dados():
    repo = Repo(":memory:")
    ana = repo.criar_colaborador("Ana")
    bia = repo.criar_colaborador("Bia")
    dia = datetime(2026, 10, 21, 9, 0)
    for i in range(4):
        _, r = repo.registrar(f"10000000000000{i}", ana["id"], dia)
    repo.marcar_erro(r["id"], None)
    for i in range(2):
        repo.registrar(f"20000000000000{i}", bia["id"], dia)
    repo.registrar("300000000000000", None, dia)
    repo.registrar("400000000000000", ana["id"], datetime(2026, 10, 20, 23, 59))
    return repo, ana, bia


def test_resumo(dados):
    repo, ana, bia = dados
    linhas = repo.resumo(*periodo("dia", date(2026, 10, 21)))
    assert linhas[0] == {"colaborador_id": ana["id"], "nome": "Ana", "cor": "#2563EB",
                         "pacotes": 4, "erros": 1, "taxa": 0.25}
    assert linhas[1]["nome"] == "Bia"
    assert (linhas[1]["pacotes"], linhas[1]["erros"], linhas[1]["taxa"]) == (2, 0, 0.0)
    sem = linhas[2]
    assert (sem["colaborador_id"], sem["nome"], sem["cor"], sem["pacotes"]) == (None, "Sem colaborador", "#DC2626", 1)


def test_listar_registros_filtros(dados):
    repo, ana, bia = dados
    inicio, fim = periodo("dia", date(2026, 10, 21))
    assert len(repo.listar_registros(inicio, fim)) == 7
    assert len(repo.listar_registros(inicio, fim, colaborador_id=ana["id"])) == 4
    assert len(repo.listar_registros(inicio, fim, sem_colaborador=True)) == 1
