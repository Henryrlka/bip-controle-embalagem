from datetime import datetime

import pytest

from bip.db import Repo
from bip.detector import Scan
from bip.servico import Servico

AGORA = datetime(2026, 10, 21, 10, 0)


def novo_servico(repo=None, calibrado=True):
    repo = repo or Repo(":memory:")
    if calibrado:
        repo.set_config("limiar_ms", "50")
    return repo, Servico(repo, relogio=lambda: AGORA)


def bip(servico, codigo="999882543964725", intervalo=10.0):
    return servico.processar_scan(Scan(codigo, intervalo))


def test_inicio_sem_ativo():
    repo = Repo(":memory:")
    ana = repo.criar_colaborador("Ana")
    repo.set_config("colaborador_ativo", str(ana["id"]))
    _, s = novo_servico(repo)
    assert s.ativo() is None


def test_bip_com_ativo():
    repo, s = novo_servico()
    ana = repo.criar_colaborador("Ana")
    s.definir_ativo(ana["id"])
    ev = bip(s)
    assert ev["tipo"] == "novo"
    assert ev["mensagem"] == "Ana"
    assert ev["rastreio"] == "999882543964725"
    assert ev["registro"]["colaborador_nome"] == "Ana"


def test_bip_sem_ativo():
    _, s = novo_servico()
    ev = bip(s)
    assert ev["tipo"] == "sem_colaborador"
    assert ev["mensagem"] == "Sem colaborador"


def test_repetido():
    repo, s = novo_servico()
    ana = repo.criar_colaborador("Ana")
    bia = repo.criar_colaborador("Bia")
    s.definir_ativo(ana["id"])
    bip(s)
    s.definir_ativo(bia["id"])
    ev = bip(s)
    assert ev["tipo"] == "repetido"
    assert ev["mensagem"] == "Já registrado no Ana"


def test_repetido_sem_colaborador():
    _, s = novo_servico()
    bip(s)
    assert bip(s)["mensagem"] == "Já registrado no Sem colaborador"


def test_desativar_ativo_limpa_ativo():
    repo, s = novo_servico()
    ana = repo.criar_colaborador("Ana")
    s.definir_ativo(ana["id"])
    s.desativar_colaborador(ana["id"])
    assert s.ativo() is None
    assert bip(s)["tipo"] == "sem_colaborador"


def test_desativar_outro_mantem_ativo():
    repo, s = novo_servico()
    ana = repo.criar_colaborador("Ana")
    bia = repo.criar_colaborador("Bia")
    s.definir_ativo(ana["id"])
    s.desativar_colaborador(bia["id"])
    assert s.ativo()["nome"] == "Ana"


def test_definir_ativo_inativo_falha():
    repo, s = novo_servico()
    ana = repo.criar_colaborador("Ana")
    repo.atualizar_colaborador(ana["id"], ativo=False)
    with pytest.raises(ValueError):
        s.definir_ativo(ana["id"])
    with pytest.raises(ValueError):
        s.definir_ativo(999)


def test_definir_ativo_none():
    repo, s = novo_servico()
    ana = repo.criar_colaborador("Ana")
    s.definir_ativo(ana["id"])
    s.definir_ativo(None)
    assert s.ativo() is None


def test_calibracao():
    repo, s = novo_servico(calibrado=False)
    assert s.precisa_calibrar()
    assert s.calibracao()["calibrando"] is True
    assert s.limiar_ms() == 300
    bip(s, "100000000000001", 8)
    assert s.calibracao()["amostras"] == 1
    bip(s, "100000000000002", 12)
    bip(s, "100000000000003", 10)
    assert s.limiar_ms() == 50
    assert s.calibracao() == {"calibrando": False, "amostras": 0, "total": 3, "limiar_ms": 50.0}
    assert not s.precisa_calibrar()
    assert len(repo.ultimos()) == 3


def test_calibracao_teto():
    _, s = novo_servico(calibrado=False)
    for i, ms in enumerate([60, 70, 50]):
        bip(s, f"10000000000000{i}", ms)
    assert s.limiar_ms() == 80


def test_recalibrar():
    _, s = novo_servico()
    assert s.limiar_ms() == 50
    s.iniciar_calibracao()
    assert s.limiar_ms() == 300


def test_eventos_desde():
    _, s = novo_servico()
    for i in range(3):
        bip(s, f"10000000000000{i}")
    assert len(s.eventos_desde(0)) == 3
    assert [e["id"] for e in s.eventos_desde(2)] == [3]
    assert s.ultimo_evento_id() == 3


def test_hoje():
    _, s = novo_servico()
    assert s.hoje() == AGORA.date()


def test_cancelar_calibracao_mantem_limiar():
    repo, s = novo_servico()
    repo.set_config("limiar_ms", "66")
    _, s = novo_servico(repo, calibrado=False)
    s.iniciar_calibracao()
    bip(s, "100000000000001", 30)
    s.cancelar_calibracao()
    assert s.calibracao()["calibrando"] is False
    assert s.calibracao()["amostras"] == 0
    assert s.limiar_ms() == 66


def test_limiar_reflete_calibracao_nova():
    _, s = novo_servico()
    s.iniciar_calibracao()
    for i, ms in enumerate([30, 35, 32]):
        bip(s, f"10000000000000{i}", ms)
    assert s.limiar_ms() == 70
