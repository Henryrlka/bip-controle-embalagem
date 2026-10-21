"""API JSON e página estática da interface."""

from flask import Flask, jsonify, request, send_from_directory

from bip.db import NomeDuplicado, Repo
from bip.relatorios import periodo
from bip.servico import Servico

DUPLICADO = "Já existe colaborador com esse nome"
HOSTS_PERMITIDOS = {"127.0.0.1", "localhost"}


def create_app(servico: Servico, repo: Repo, static_dir: str) -> Flask:
    app = Flask(__name__, static_folder=static_dir, static_url_path="/static")
    app.json.ensure_ascii = False

    def erro(mensagem: str, status: int):
        return jsonify({"erro": mensagem}), status

    @app.before_request
    def proteger():
        # Bloqueia DNS rebinding (Host de outro site) e CSRF: navegador só manda
        # application/json para outra origem depois de preflight CORS, que esta API não aceita.
        if request.host.rsplit(":", 1)[0] not in HOSTS_PERMITIDOS:
            return erro("Host não permitido", 403)
        if request.method in ("POST", "PATCH", "DELETE") and not request.is_json:
            return erro("Envie application/json", 415)

    def estado() -> dict:
        return {"ativo": servico.ativo(), "calibracao": servico.calibracao(),
                "ultimo_evento_id": servico.ultimo_evento_id()}

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
        try:
            servico.definir_ativo((request.get_json(silent=True) or {}).get("colaborador_id"))
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
        nome = (request.get_json(silent=True) or {}).get("nome") or ""
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
        dados = request.get_json(silent=True) or {}
        try:
            repo.atualizar_colaborador(id, nome=dados.get("nome"), cor=dados.get("cor"))
        except NomeDuplicado:
            return erro(DUPLICADO, 409)
        except ValueError:
            return erro("Nome vazio", 400)
        if dados.get("ativo") is False:
            servico.desativar_colaborador(id)
        elif dados.get("ativo") is True:
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
        colaborador_id = (request.get_json(silent=True) or {}).get("colaborador_id")
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
        obs = ((request.get_json(silent=True) or {}).get("obs") or "").strip()
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
            return jsonify(repo.listar_registros(inicio, fim, colaborador_id=int(alvo)))
        return jsonify(repo.listar_registros(inicio, fim))

    @app.post("/api/calibracao")
    def post_calibracao():
        servico.iniciar_calibracao()
        return jsonify(servico.calibracao())

    return app
