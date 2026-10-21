from datetime import datetime

import pytest

from bip.db import NomeDuplicado, Repo

AGORA = datetime(2026, 10, 21, 10, 0)


@pytest.fixture
def repo():
    return Repo(":memory:")


def test_criar_colaborador_paleta(repo):
    primeiro = repo.criar_colaborador("Ana")
    assert primeiro["cor"] == "#2563EB"
    assert primeiro["som_hz"] == 440
    assert primeiro["ativo"] is True
    for i in range(7):
        repo.criar_colaborador(f"C{i}")
    nono = repo.criar_colaborador("Nono")
    assert nono["cor"] == "#2563EB"


def test_nome_vazio(repo):
    with pytest.raises(ValueError):
        repo.criar_colaborador("   ")


def test_nome_duplicado(repo):
    repo.criar_colaborador("Ana")
    with pytest.raises(NomeDuplicado):
        repo.criar_colaborador(" ana ")


def test_renomear_duplicado(repo):
    repo.criar_colaborador("Ana")
    bia = repo.criar_colaborador("Bia")
    with pytest.raises(NomeDuplicado):
        repo.atualizar_colaborador(bia["id"], nome="ANA")


def test_desativado_some_da_lista(repo):
    ana = repo.criar_colaborador("Ana")
    repo.atualizar_colaborador(ana["id"], ativo=False)
    assert repo.listar_colaboradores() == []
    todos = repo.listar_colaboradores(incluir_inativos=True)
    assert [c["nome"] for c in todos] == ["Ana"]
    assert todos[0]["ativo"] is False


def test_registrar_e_repetido(repo):
    ana = repo.criar_colaborador("Ana")
    bia = repo.criar_colaborador("Bia")
    criado, r = repo.registrar("999882543964725", ana["id"], AGORA)
    assert criado is True
    assert r["colaborador_nome"] == "Ana"
    assert r["bipado_em"] == "2026-10-21T10:00:00"
    criado, r2 = repo.registrar("999882543964725", bia["id"], AGORA)
    assert criado is False
    assert r2["colaborador_nome"] == "Ana"


def test_registrar_sem_colaborador(repo):
    _, r = repo.registrar("999882543964725", None, AGORA)
    assert r["colaborador_id"] is None
    assert r["colaborador_nome"] is None


def test_mover_e_excluir(repo):
    ana = repo.criar_colaborador("Ana")
    bia = repo.criar_colaborador("Bia")
    _, r = repo.registrar("999882543964725", ana["id"], AGORA)
    assert repo.mover(r["id"], bia["id"])["colaborador_nome"] == "Bia"
    assert repo.mover(r["id"], None)["colaborador_nome"] is None
    repo.excluir(r["id"])
    assert repo.buscar("999882543964725") == []
    assert repo.registrar("999882543964725", ana["id"], AGORA)[0] is True


def test_erro(repo):
    _, r = repo.registrar("999882543964725", None, AGORA)
    r = repo.marcar_erro(r["id"], "mandou bermuda")
    assert r["erro"] is True
    assert r["erro_obs"] == "mandou bermuda"
    r = repo.desmarcar_erro(r["id"])
    assert r["erro"] is False
    assert r["erro_obs"] is None


def test_buscar_parcial(repo):
    repo.registrar("999882543964725", None, AGORA)
    repo.registrar("111222333444555", None, AGORA)
    assert [r["rastreio"] for r in repo.buscar("43964")] == ["999882543964725"]
    for i in range(60):
        repo.registrar(f"77700000000{i:04d}", None, AGORA)
    assert len(repo.buscar("777")) == 50


def test_buscar_ignora_maiusculas(repo):
    repo.registrar("BR1234567890BR", None, AGORA)
    assert len(repo.buscar("br12")) == 1


def test_ultimos(repo):
    for i in range(25):
        repo.registrar(f"5550000000{i:05d}", None, AGORA)
    ultimos = repo.ultimos()
    assert len(ultimos) == 20
    assert ultimos[0]["rastreio"] == "555000000000024"


def test_historico_preservado_ao_desativar(repo):
    ana = repo.criar_colaborador("Ana")
    _, r = repo.registrar("999882543964725", ana["id"], AGORA)
    repo.atualizar_colaborador(ana["id"], ativo=False)
    assert repo.buscar("999882543964725")[0]["colaborador_nome"] == "Ana"


def test_id_maior_que_o_sqlite_nao_existe(repo):
    assert repo.obter_colaborador(10**20) is None
    assert repo.obter_registro(10**20) is None


def test_config(repo):
    assert repo.get_config("x") is None
    assert repo.get_config("x", "p") == "p"
    repo.set_config("x", "1")
    assert repo.get_config("x") == "1"
    repo.del_config("x")
    assert repo.get_config("x") is None
