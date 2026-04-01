from app.services.crypto_service import decrypt, encrypt


def test_encrypt_decrypt_roundtrip():
    token = encrypt("secret")
    assert decrypt(token) == "secret"


def test_encrypt_is_nondeterministic():
    t1 = encrypt("same")
    t2 = encrypt("same")
    assert t1 != t2


def test_encrypt_returns_string():
    token = encrypt("hello")
    assert isinstance(token, str)
    assert token != "hello"
