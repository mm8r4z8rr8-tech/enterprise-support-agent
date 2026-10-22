
from app.security import hash_password, verify_password
from jose import JWTError

from app.security import create_access_token, decode_access_token

def test_hash_password_does_not_store_plain_password():
    password = "TestPassword123!"

    hashed_password = hash_password(password)

    # 哈希结果不应该等于原始密码
    assert hashed_password != password

    # 验证正确密码应该成功
    assert verify_password(password, hashed_password)


def test_verify_password_rejects_wrong_password():
    password = "TestPassword123!"
    wrong_password = "WrongPassword123!"

    hashed_password = hash_password(password)

    # 错误密码应该验证失败
    assert not verify_password(
        wrong_password,
        hashed_password,
    )
def test_create_and_decode_access_token():
    # 模拟登录成功后写入令牌的用户标识
    data = {"sub": "1"}

    token = create_access_token(data)
    decoded_data = decode_access_token(token)

    assert isinstance(token, str)
    assert decoded_data["sub"] == "1"
    assert "exp" in decoded_data


def test_decode_access_token_rejects_invalid_token():
    # 无效令牌应该无法通过验证
    try:
        decode_access_token("invalid.token.value")
    except JWTError:
        pass
    else:
        assert False, "Invalid token should raise JWTError"