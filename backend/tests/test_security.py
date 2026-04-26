from app.core.security import hash_password, verify_password


def test_hash_is_not_plaintext():
    h = hash_password("secret123")
    assert h != "secret123"
    assert h.startswith("$2")  # bcrypt prefix


def test_verify_correct_password():
    h = hash_password("correct horse battery staple")
    assert verify_password("correct horse battery staple", h) is True


def test_verify_wrong_password_fails():
    h = hash_password("right")
    assert verify_password("wrong", h) is False


def test_hash_is_salted_so_same_input_yields_different_output():
    a = hash_password("same")
    b = hash_password("same")
    assert a != b
    assert verify_password("same", a)
    assert verify_password("same", b)
