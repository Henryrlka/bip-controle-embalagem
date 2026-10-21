from datetime import datetime
from pathlib import Path

import pytest

from bip.db import Repo
from bip.detector import Scan
from bip.servico import Servico
from bip.web import create_app

AGORA = datetime(2026, 10, 21, 10, 0)
STATIC = str(Path(__file__).resolve().parent.parent / "bip" / "static")
DUPLICADO = "Já existe colaborador com esse nome"


@pytest.fixture
def ctx():
    repo = Repo(":memory:")
    repo.set_config("limiar_ms", "50")
    servico = Servico(repo, relogio=lambda: AGORA)
    app = create_app(servico, repo, STATIC)
    return app.test_client(), servico, repo


def bip(servico, codigo="999882543964725"):
    return servico.processar_scan(Scan(codigo, 10))


def test_index(ctx):
    cliente, _, _ = ctx
    assert cliente.get("/").status_code == 200


def test_criar_e_listar_colaborador(ctx):
    cliente, _, _ = ctx
    r = cliente.post("/api/colaboradores", json={"nome": "Ana"})
    assert r.status_code == 201
    assert r.json["nome"] == "Ana"
    assert len(cliente.get("/api/colaboradores").json) == 1


def test_criar_vazio_400(ctx):
    cliente, _, _ = ctx
    assert cliente.post("/api/colaboradores", json={"nome": " "}).status_code == 400


def test_criar_duplicado_409(ctx):
    cliente, _, _ = ctx
    cliente.post("/api/colaboradores", json={"nome": "Ana"})
    r = cliente.post("/api/colaboradores", json={"nome": "ana"})
    assert r.status_code == 409
    assert r.json["erro"] == DUPLICADO


def test_renomear_duplicado_409(ctx):
    cliente, _, _ = ctx
    cliente.post("/api/colaboradores", json={"nome": "Ana"})
    bia = cliente.post("/api/colaboradores", json={"nome": "Bia"}).json
    r = cliente.patch(f"/api/colaboradores/{bia['id']}", json={"nome": "Ana"})
    assert r.status_code == 409
    assert r.json["erro"] == DUPLICADO


def test_desativar_pela_api_limpa_ativo(ctx):
    cliente, servico, _ = ctx
    ana = cliente.post("/api/colaboradores", json={"nome": "Ana"}).json
    cliente.post("/api/ativo", json={"colaborador_id": ana["id"]})
    r = cliente.patch(f"/api/colaboradores/{ana['id']}", json={"ativo": False})
    assert r.json["ativo"] is False
    assert servico.ativo() is None
    assert cliente.get("/api/colaboradores").json == []
    assert len(cliente.get("/api/colaboradores?inativos=1").json) == 1


def test_ativo_e_estado(ctx):
    cliente, _, _ = ctx
    ana = cliente.post("/api/colaboradores", json={"nome": "Ana"}).json
    r = cliente.post("/api/ativo", json={"colaborador_id": ana["id"]})
    assert r.json["ativo"]["nome"] == "Ana"
    assert cliente.get("/api/estado").json["ativo"]["nome"] == "Ana"
    assert cliente.post("/api/ativo", json={"colaborador_id": None}).json["ativo"] is None
    assert cliente.post("/api/ativo", json={"colaborador_id": 999}).status_code == 400


def test_eventos(ctx):
    cliente, servico, _ = ctx
    bip(servico)
    eventos = cliente.get("/api/eventos?desde=0").json
    assert len(eventos) == 1
    assert eventos[0]["tipo"] == "sem_colaborador"
    assert cliente.get("/api/estado").json["ultimo_evento_id"] == 1
    assert cliente.get("/api/eventos?desde=1").json == []


def test_ultimos(ctx):
    cliente, servico, _ = ctx
    bip(servico)
    assert cliente.get("/api/registros/ultimos").json[0]["rastreio"] == "999882543964725"


def test_busca_curta_vazia(ctx):
    cliente, servico, _ = ctx
    bip(servico)
    assert cliente.get("/api/busca?q=99").json == []
    assert len(cliente.get("/api/busca?q=9998").json) == 1


def test_mover_excluir_erro(ctx):
    cliente, servico, _ = ctx
    bia = cliente.post("/api/colaboradores", json={"nome": "Bia"}).json
    rid = bip(servico)["registro"]["id"]
    assert cliente.patch(f"/api/registros/{rid}", json={"colaborador_id": bia["id"]}).json["colaborador_nome"] == "Bia"
    r = cliente.post(f"/api/registros/{rid}/erro", json={"obs": "x"}).json
    assert (r["erro"], r["erro_obs"]) == (True, "x")
    assert cliente.delete(f"/api/registros/{rid}/erro", json={}).json["erro"] is False
    assert cliente.delete(f"/api/registros/{rid}", json={}).status_code == 204
    assert cliente.patch(f"/api/registros/{rid}", json={"colaborador_id": None}).status_code == 404


def test_relatorio(ctx):
    cliente, servico, _ = ctx
    bip(servico)
    linhas = cliente.get("/api/relatorio?periodo=dia").json
    assert linhas[0]["nome"] == "Sem colaborador"
    assert linhas[0]["pacotes"] == 1


def test_relatorio_periodo_invalido(ctx):
    cliente, _, _ = ctx
    assert cliente.get("/api/relatorio?periodo=ano").status_code == 400


def test_relatorio_lista_sem(ctx):
    cliente, servico, _ = ctx
    ana = cliente.post("/api/colaboradores", json={"nome": "Ana"}).json
    bip(servico, "100000000000001")
    servico.definir_ativo(ana["id"])
    bip(servico, "100000000000002")
    sem = cliente.get("/api/relatorio/lista?periodo=dia&colaborador_id=sem").json
    assert [r["rastreio"] for r in sem] == ["100000000000001"]
    dela = cliente.get(f"/api/relatorio/lista?periodo=dia&colaborador_id={ana['id']}").json
    assert [r["rastreio"] for r in dela] == ["100000000000002"]


def test_calibracao(ctx):
    cliente, _, _ = ctx
    r = cliente.post("/api/calibracao", json={}).json
    assert r["calibrando"] is True
    assert cliente.get("/api/estado").json["calibracao"]["calibrando"] is True


def test_host_estranho_bloqueado(ctx):
    cliente, _, _ = ctx
    assert cliente.get("/api/estado", headers={"Host": "evil.example:8765"}).status_code == 403
    assert cliente.get("/api/estado", headers={"Host": "127.0.0.1:8765"}).status_code == 200


def test_alteracao_sem_json_bloqueada(ctx):
    cliente, servico, _ = ctx
    r = cliente.post("/api/calibracao", data="x", content_type="text/plain")
    assert r.status_code == 415
    assert servico.calibracao()["calibrando"] is False
    assert cliente.post("/api/calibracao", json={}).status_code == 200


def test_cancelar_calibracao(ctx):
    cliente, servico, _ = ctx
    cliente.post("/api/calibracao", json={})
    r = cliente.post("/api/calibracao/cancelar", json={})
    assert r.status_code == 200
    assert r.json["calibrando"] is False
    assert servico.limiar_ms() == 50


def test_estado_tem_sessao_e_escuta(ctx):
    cliente, _, _ = ctx
    e = cliente.get("/api/estado").json
    assert isinstance(e["sessao"], str) and len(e["sessao"]) >= 8
    assert e["escuta_ativa"] is True
    assert cliente.get("/api/estado").json["sessao"] == e["sessao"]


def test_sessao_muda_entre_inicios():
    repo = Repo(":memory:")
    a = create_app(Servico(repo), repo, STATIC).test_client().get("/api/estado").json["sessao"]
    b = create_app(Servico(repo), repo, STATIC).test_client().get("/api/estado").json["sessao"]
    assert a != b


def test_escuta_parada():
    repo = Repo(":memory:")
    app = create_app(Servico(repo), repo, STATIC, escuta_ativa=lambda: False)
    assert app.test_client().get("/api/estado").json["escuta_ativa"] is False
