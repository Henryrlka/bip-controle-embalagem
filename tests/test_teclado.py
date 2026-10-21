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
