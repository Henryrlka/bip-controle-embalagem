"""API JSON e página estática da interface."""

import logging
import re
from collections.abc import Callable

from flask import Flask, jsonify, request, send_from_directory
from werkzeug.exceptions import HTTPException, MethodNotAllowed

from bip.db import MAX_ID, NomeDuplicado, Repo
from bip.relatorios import periodo
from bip.servico import Servico

log = logging.getLogger(__name__)

DUPLICADO = "Já existe colaborador com esse nome"
HOSTS_PERMITIDOS = {"127.0.0.1", "localhost"}
COR = re.compile(r"#[0-9A-Fa-f]{6}")
MAX_OBS = 500
MENSAGENS_HTTP = {404: "Rota não encontrada", 405: "Método não permitido", 500: "Erro interno do Bip"}


class EntradaInvalida(Exception):
    pass


def _corpo_valido() -> bool:
    return isinstance(request.get_json(silent=True), dict) or not request.get_data()


def _corpo() -> dict:
    # proteger() já garantiu: corpo vazio ou objeto JSON.
    return request.get_json(silent=True) or {}


def _texto(valor, mensagem: str) -> str | None:
    if valor is None or isinstance(valor, str):
        return valor
    raise EntradaInvalida(mensagem)


def _id(valor) -> int | None:
    # type() e não isinstance(): True/False são int para o Python.
    if valor is None or (type(valor) is int and abs(valor) <= MAX_ID):
        return valor
    raise EntradaInvalida("colaborador_id inválido")


def _id_de_texto(valor: str) -> int:
    try:
        return _id(int(valor))
    except ValueError:
        raise EntradaInvalida("colaborador_id inválido") from None


def create_app(servico: Servico, repo: Repo, static_dir: str,
               escuta_ativa: Callable[[], bool] = lambda: True) -> Flask:
    app = Flask(__name__, static_folder=static_dir, static_url_path="/static")
    app.json.ensure_ascii = False

    def erro(mensagem: str, status: int):
        return jsonify({"erro": mensagem}), status

    # A tela sempre espera JSON, inclusive nos erros.

    @app.errorhandler(EntradaInvalida)
    def entrada_invalida(e: EntradaInvalida):
        return erro(str(e), 400)

    @app.errorhandler(HTTPException)
    def erro_http(e: HTTPException):
        resposta, status = erro(MENSAGENS_HTTP.get(e.code, "Requisição inválida"), e.code)
        if isinstance(e, MethodNotAllowed) and e.valid_methods:
            resposta.headers["Allow"] = ", ".join(e.valid_methods)
        return resposta, status

    @app.errorhandler(Exception)
    def erro_interno(e: Exception):
        log.exception("Erro em %s %s", request.method, request.path)
        return erro("Erro interno do Bip", 500)

    @app.before_request
    def proteger():
        # Bloqueia DNS rebinding (Host de outro site) e CSRF: navegador só manda
        # application/json para outra origem depois de preflight CORS, que esta API não aceita.
        if request.host.rsplit(":", 1)[0] not in HOSTS_PERMITIDOS:
            return erro("Host não permitido", 403)
        if request.method in ("POST", "PATCH", "DELETE") and not request.is_json:
            return erro("Envie application/json", 415)
        if request.method in ("POST", "PATCH") and not _corpo_valido():
            return erro("JSON inválido", 400)

    def estado() -> dict:
        return {"ativo": servico.ativo(), "calibracao": servico.calibracao(),
                "ultimo_evento_id": servico.ultimo_evento_id(), "sessao": servico.sessao,
                "escuta_ativa": bool(escuta_ativa())}

    def intervalo():
        return periodo(request.args.get("periodo", "dia"), servico.hoje())

    @app.get("/")
    def index():
        return send_from_directory(static_dir, "index.html")

    @app.get("/api/estado")
    def get_estado():
        return jsonify(estado())

    @app.post("/api/ativo")
    def post_ativo():
        colaborador_id = _id(_corpo().get("colaborador_id"))
        try:
            servico.definir_ativo(colaborador_id)
        except ValueError:
            return erro("Colaborador inexistente ou inativo", 400)
        return jsonify(estado())

    @app.get("/api/eventos")
    def get_eventos():
        return jsonify(servico.eventos_desde(request.args.get("desde", 0, type=int)))

    @app.get("/api/colaboradores")
    def get_colaboradores():
        return jsonify(repo.listar_colaboradores(incluir_inativos=request.args.get("inativos") == "1"))

    @app.post("/api/colaboradores")
    def post_colaborador():
        nome = _texto(_corpo().get("nome"), "Nome inválido") or ""
        try:
            return jsonify(repo.criar_colaborador(nome)), 201
        except NomeDuplicado:
            return erro(DUPLICADO, 409)
        except ValueError:
            return erro("Nome vazio", 400)

    @app.patch("/api/colaboradores/<int:id>")
    def patch_colaborador(id: int):
        if repo.obter_colaborador(id) is None:
            return erro("Colaborador não encontrado", 404)
        dados = _corpo()
        # Valida tudo antes de gravar qualquer coisa.
        nome = _texto(dados.get("nome"), "Nome inválido")
        cor = dados.get("cor")
        if cor is not None and not (isinstance(cor, str) and COR.fullmatch(cor)):
            return erro("Cor inválida", 400)
        ativo = dados.get("ativo")
        if ativo is not None and not isinstance(ativo, bool):
            return erro("ativo inválido", 400)
        try:
            repo.atualizar_colaborador(id, nome=nome, cor=cor)
        except NomeDuplicado:
            return erro(DUPLICADO, 409)
        except ValueError:
            return erro("Nome vazio", 400)
        if ativo is False:
            servico.desativar_colaborador(id)
        elif ativo is True:
            repo.atualizar_colaborador(id, ativo=True)
        return jsonify(repo.obter_colaborador(id))

    @app.get("/api/registros/ultimos")
    def get_ultimos():
        return jsonify(repo.ultimos())

    @app.get("/api/busca")
    def get_busca():
        q = request.args.get("q", "").strip()
        return jsonify(repo.buscar(q) if len(q) >= 3 else [])

    @app.patch("/api/registros/<int:id>")
    def patch_registro(id: int):
        if repo.obter_registro(id) is None:
            return erro("Registro não encontrado", 404)
        colaborador_id = _id(_corpo().get("colaborador_id"))
        if colaborador_id is not None and repo.obter_colaborador(colaborador_id) is None:
            return erro("Colaborador não encontrado", 400)
        return jsonify(repo.mover(id, colaborador_id))

    @app.delete("/api/registros/<int:id>")
    def delete_registro(id: int):
        if repo.obter_registro(id) is None:
            return erro("Registro não encontrado", 404)
        repo.excluir(id)
        return "", 204

    @app.post("/api/registros/<int:id>/erro")
    def post_erro(id: int):
        if repo.obter_registro(id) is None:
            return erro("Registro não encontrado", 404)
        obs = (_texto(_corpo().get("obs"), "Observação inválida") or "").strip()
        if len(obs) > MAX_OBS:
            return erro(f"Observação muito longa (máximo {MAX_OBS} caracteres)", 400)
        return jsonify(repo.marcar_erro(id, obs or None))

    @app.delete("/api/registros/<int:id>/erro")
    def delete_erro(id: int):
        if repo.obter_registro(id) is None:
            return erro("Registro não encontrado", 404)
        return jsonify(repo.desmarcar_erro(id))

    @app.get("/api/relatorio")
    def get_relatorio():
        try:
            return jsonify(repo.resumo(*intervalo()))
        except ValueError:
            return erro("Período inválido", 400)

    @app.get("/api/relatorio/lista")
    def get_relatorio_lista():
        try:
            inicio, fim = intervalo()
        except ValueError:
            return erro("Período inválido", 400)
        alvo = request.args.get("colaborador_id")
        if alvo == "sem":
            return jsonify(repo.listar_registros(inicio, fim, sem_colaborador=True))
        if alvo:
            return jsonify(repo.listar_registros(inicio, fim, colaborador_id=_id_de_texto(alvo)))
        return jsonify(repo.listar_registros(inicio, fim))

    @app.post("/api/calibracao")
    def post_calibracao():
        servico.iniciar_calibracao()
        return jsonify(servico.calibracao())

    @app.post("/api/calibracao/cancelar")
    def post_cancelar_calibracao():
        servico.cancelar_calibracao()
        return jsonify(servico.calibracao())

    return app
