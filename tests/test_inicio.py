import logging
import webbrowser

from bip import inicio

URL = "http://127.0.0.1:8765"


def preparar(monkeypatch, tmp_path, padrao_falha=False) -> list[str]:
    exe = tmp_path / "chrome.exe"
    exe.write_bytes(b"")
    monkeypatch.setattr(inicio, "_navegadores", lambda: [exe])

    def popen(*args, **kwargs):
        raise OSError("acesso negado")

    monkeypatch.setattr(inicio.subprocess, "Popen", popen)
    abertos = []

    def abrir(url, *args, **kwargs):
        abertos.append(url)
        if padrao_falha:
            raise webbrowser.Error("sem navegador")
        return True

    monkeypatch.setattr(inicio.webbrowser, "open", abrir)
    return abertos


def erros(caplog) -> list[logging.LogRecord]:
    return [r for r in caplog.records if r.levelno == logging.ERROR and r.name == "bip.inicio"]


def test_falha_ao_abrir_janela_cai_no_navegador_padrao(monkeypatch, tmp_path, caplog):
    abertos = preparar(monkeypatch, tmp_path)
    with caplog.at_level(logging.WARNING, logger="bip.inicio"):
        inicio.abrir_janela(URL)
    assert abertos == [URL]
    assert len(erros(caplog)) == 1
    assert erros(caplog)[0].exc_info[0] is OSError


def test_falha_tambem_no_navegador_padrao_so_registra(monkeypatch, tmp_path, caplog):
    abertos = preparar(monkeypatch, tmp_path, padrao_falha=True)
    with caplog.at_level(logging.WARNING, logger="bip.inicio"):
        inicio.abrir_janela(URL)
    assert abertos == [URL]
    assert [r.exc_info[0] for r in erros(caplog)] == [OSError, webbrowser.Error]
