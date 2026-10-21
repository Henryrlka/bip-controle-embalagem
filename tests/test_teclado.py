from pynput.keyboard import Key, KeyCode

from bip.teclado import token_de


def test_token_char():
    assert token_de(KeyCode.from_char("7")) == "7"
    assert token_de(KeyCode.from_char("b")) == "b"


def test_token_numpad():
    assert token_de(KeyCode.from_vk(99)) == "3"
    assert token_de(KeyCode.from_vk(96)) == "0"


def test_token_enter_mod_outra():
    assert token_de(Key.enter) == "ENTER"
    assert token_de(Key.shift) == "MOD"
    assert token_de(Key.caps_lock) == "MOD"
    assert token_de(Key.tab) == "OUTRA"
    assert token_de(KeyCode.from_vk(200)) == "OUTRA"


def test_evento_injetado_ignorado():
    from bip.teclado import LLKHF_INJECTED, aceitar_evento
    assert aceitar_evento(0, aceitar_simulado=False) is True
    assert aceitar_evento(LLKHF_INJECTED, aceitar_simulado=False) is False
    assert aceitar_evento(LLKHF_INJECTED, aceitar_simulado=True) is True
