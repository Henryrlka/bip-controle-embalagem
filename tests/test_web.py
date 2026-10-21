import logging
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


# Entrada malformada: sempre 400 com {"erro": ...}, nunca 500.

def resposta(r):
    return r.status_code, r.json


ROTAS_COM_CORPO = [
    ("POST", "/api/ativo"),
    ("POST", "/api/colaboradores"),
    ("PATCH", "/api/colaboradores/{c}"),
    ("PATCH", "/api/registros/{r}"),
    ("POST", "/api/registros/{r}/erro"),
    ("POST", "/api/calibracao"),
    ("POST", "/api/calibracao/cancelar"),
]


@pytest.mark.parametrize("metodo,rota", ROTAS_COM_CORPO)
def test_json_que_nao_e_objeto_400(ctx, metodo, rota):
    cliente, servico, repo = ctx
    url = rota.format(c=repo.criar_colaborador("Ana")["id"], r=bip(servico)["registro"]["id"])
    for corpo in ["[]", '"x"', "5", "null", "{"]:
        r = cliente.open(url, method=metodo, data=corpo, content_type="application/json")
        assert resposta(r) == (400, {"erro": "JSON inválido"}), corpo


def test_corpo_json_vazio_aceito(ctx):
    cliente, _, _ = ctx
    assert cliente.post("/api/calibracao", data="", content_type="application/json").status_code == 200


def test_relatorio_lista_colaborador_id_invalido(ctx):
    cliente, _, _ = ctx
    for valor in ["abc", "1.5", "99999999999999999999"]:
        r = cliente.get(f"/api/relatorio/lista?periodo=dia&colaborador_id={valor}")
        assert resposta(r) == (400, {"erro": "colaborador_id inválido"}), valor


@pytest.mark.parametrize("nome", [5, ["Ana"], True, {"nome": "Ana"}])
def test_criar_nome_nao_texto_400(ctx, nome):
    cliente, _, _ = ctx
    assert resposta(cliente.post("/api/colaboradores", json={"nome": nome})) == (400, {"erro": "Nome inválido"})
    assert cliente.get("/api/colaboradores").json == []


@pytest.mark.parametrize("corpo", [{}, {"nome": None}, {"nome": ""}, {"nome": "  "}])
def test_criar_sem_nome_400(ctx, corpo):
    cliente, _, _ = ctx
    assert resposta(cliente.post("/api/colaboradores", json=corpo)) == (400, {"erro": "Nome vazio"})


@pytest.mark.parametrize("corpo,mensagem", [
    ({"nome": 5}, "Nome inválido"),
    ({"nome": ["Bia"]}, "Nome inválido"),
    ({"nome": " "}, "Nome vazio"),
    ({"cor": "red"}, "Cor inválida"),
    ({"cor": "#12345"}, "Cor inválida"),
    ({"cor": "#1234567"}, "Cor inválida"),
    ({"cor": "#GGGGGG"}, "Cor inválida"),
    ({"cor": "#123456\n"}, "Cor inválida"),
    ({"cor": 123456}, "Cor inválida"),
    ({"ativo": "false"}, "ativo inválido"),
    ({"ativo": 0}, "ativo inválido"),
    ({"nome": "Bia", "ativo": 1}, "ativo inválido"),
    ({"nome": "Bia", "cor": "x"}, "Cor inválida"),
])
def test_editar_colaborador_invalido_400_sem_mudar_nada(ctx, corpo, mensagem):
    cliente, _, repo = ctx
    ana = repo.criar_colaborador("Ana")
    assert resposta(cliente.patch(f"/api/colaboradores/{ana['id']}", json=corpo)) == (400, {"erro": mensagem})
    assert repo.obter_colaborador(ana["id"]) == ana


def test_editar_cor_valida(ctx):
    cliente, _, repo = ctx
    ana = repo.criar_colaborador("Ana")
    r = cliente.patch(f"/api/colaboradores/{ana['id']}", json={"cor": "#a1B2c3"})
    assert r.status_code == 200
    assert r.json["cor"] == "#a1B2c3"


IDS_INVALIDOS = [True, False, "1", [1], 1.0, 1.5, {"id": 1}, 10**30]


@pytest.mark.parametrize("valor", IDS_INVALIDOS)
def test_ativo_colaborador_id_invalido_400(ctx, valor):
    cliente, servico, repo = ctx
    ana = repo.criar_colaborador("Ana")
    servico.definir_ativo(ana["id"])
    r = cliente.post("/api/ativo", json={"colaborador_id": valor})
    assert resposta(r) == (400, {"erro": "colaborador_id inválido"})
    assert servico.ativo()["id"] == ana["id"]


@pytest.mark.parametrize("valor", IDS_INVALIDOS)
def test_mover_colaborador_id_invalido_400(ctx, valor):
    cliente, servico, repo = ctx
    ana = repo.criar_colaborador("Ana")
    servico.definir_ativo(ana["id"])
    rid = bip(servico)["registro"]["id"]
    r = cliente.patch(f"/api/registros/{rid}", json={"colaborador_id": valor})
    assert resposta(r) == (400, {"erro": "colaborador_id inválido"})
    assert repo.obter_registro(rid)["colaborador_id"] == ana["id"]


@pytest.mark.parametrize("obs", [5, ["x"], True, {"obs": "x"}])
def test_erro_obs_nao_texto_400(ctx, obs):
    cliente, servico, repo = ctx
    rid = bip(servico)["registro"]["id"]
    r = cliente.post(f"/api/registros/{rid}/erro", json={"obs": obs})
    assert resposta(r) == (400, {"erro": "Observação inválida"})
    assert repo.obter_registro(rid)["erro"] is False


def test_erro_obs_muito_longa_400(ctx):
    cliente, servico, repo = ctx
    rid = bip(servico)["registro"]["id"]
    r = cliente.post(f"/api/registros/{rid}/erro", json={"obs": "x" * 501})
    assert resposta(r) == (400, {"erro": "Observação muito longa (máximo 500 caracteres)"})
    assert repo.obter_registro(rid)["erro"] is False
    r = cliente.post(f"/api/registros/{rid}/erro", json={"obs": "  " + "x" * 500 + "  "})
    assert r.status_code == 200
    assert r.json["erro_obs"] == "x" * 500


@pytest.mark.parametrize("corpo", [{}, {"obs": None}, {"obs": "  "}])
def test_erro_sem_obs(ctx, corpo):
    cliente, servico, _ = ctx
    rid = bip(servico)["registro"]["id"]
    r = cliente.post(f"/api/registros/{rid}/erro", json=corpo)
    assert (r.status_code, r.json["erro"], r.json["erro_obs"]) == (200, True, None)


# Erros sempre em JSON

def test_rota_api_desconhecida_404_json(ctx):
    cliente, _, _ = ctx
    assert resposta(cliente.get("/api/nada")) == (404, {"erro": "Rota não encontrada"})
    assert resposta(cliente.post("/api/nada", json={})) == (404, {"erro": "Rota não encontrada"})


def test_id_na_rota_maior_que_o_sqlite_404(ctx):
    cliente, _, _ = ctx
    grande = 10**20
    r = cliente.patch(f"/api/colaboradores/{grande}", json={})
    assert resposta(r) == (404, {"erro": "Colaborador não encontrado"})
    for metodo, rota in [("PATCH", f"/api/registros/{grande}"), ("DELETE", f"/api/registros/{grande}"),
                         ("POST", f"/api/registros/{grande}/erro"), ("DELETE", f"/api/registros/{grande}/erro")]:
        r = cliente.open(rota, method=metodo, json={})
        assert resposta(r) == (404, {"erro": "Registro não encontrado"}), (metodo, rota)


def test_metodo_errado_405_json(ctx):
    cliente, _, _ = ctx
    r = cliente.get("/api/calibracao")
    assert resposta(r) == (405, {"erro": "Método não permitido"})
    assert "POST" in r.headers["Allow"]


def test_excecao_inesperada_500_json_e_log(ctx, monkeypatch, caplog):
    cliente, _, repo = ctx

    def quebra(*args, **kwargs):
        raise RuntimeError("disco cheio")

    monkeypatch.setattr(repo, "ultimos", quebra)
    with caplog.at_level(logging.ERROR, logger="bip.web"):
        r = cliente.get("/api/registros/ultimos")
    assert resposta(r) == (500, {"erro": "Erro interno do Bip"})
    erros = [rec for rec in caplog.records if rec.levelno == logging.ERROR and rec.name == "bip.web"]
    assert erros and erros[0].exc_info[0] is RuntimeError


def test_guarda_vem_antes_dos_erros_json(ctx):
    cliente, _, _ = ctx
    assert resposta(cliente.get("/api/nada", headers={"Host": "evil.example"})) == (403, {"erro": "Host não permitido"})
    r = cliente.post("/api/nada", data="[]", content_type="text/plain")
    assert resposta(r) == (415, {"erro": "Envie application/json"})
