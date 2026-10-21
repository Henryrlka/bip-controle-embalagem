"""Coisas do Windows: pasta de dados, início automático, instância única e janela do navegador."""

import logging
import os
import socket
import subprocess
import sys
import webbrowser
from pathlib import Path

log = logging.getLogger(__name__)

CHAVE_RUN = r"Software\Microsoft\Windows\CurrentVersion\Run"


def pasta_dados() -> Path:
    pasta = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "Bip"
    pasta.mkdir(parents=True, exist_ok=True)
    return pasta


def caminho_static() -> str:
    if getattr(sys, "frozen", False):
        return str(Path(sys._MEIPASS) / "bip" / "static")
    return str(Path(__file__).resolve().parent / "static")


def ja_rodando(porta: int) -> bool:
    with socket.socket() as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", porta)) == 0


def registrar_autostart(exe: str) -> None:
    import winreg

    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, CHAVE_RUN, 0, winreg.KEY_SET_VALUE) as chave:
        winreg.SetValueEx(chave, "Bip", 0, winreg.REG_SZ, f'"{exe}"')


def _navegadores() -> list[Path]:
    pf = os.environ.get("ProgramFiles", r"C:\Program Files")
    pf86 = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
    local = os.environ.get("LOCALAPPDATA", "")
    return [
        Path(pf) / "Google/Chrome/Application/chrome.exe",
        Path(pf86) / "Google/Chrome/Application/chrome.exe",
        Path(local) / "Google/Chrome/Application/chrome.exe",
        Path(pf86) / "Microsoft/Edge/Application/msedge.exe",
        Path(pf) / "Microsoft/Edge/Application/msedge.exe",
    ]


def abrir_janela(url: str) -> None:
    # Roda num Timer sem console: exceção solta aqui some sem deixar rastro, então só registra.
    for exe in _navegadores():
        if exe.is_file():
            try:
                subprocess.Popen([str(exe), f"--app={url}", "--window-size=480,900"])
                return
            except Exception:
                log.exception("Falha ao abrir %s", exe)
    log.warning("Chrome/Edge não encontrado ou falhou, abrindo navegador padrão")
    try:
        webbrowser.open(url)
    except Exception:
        log.exception("Falha ao abrir o navegador padrão")
