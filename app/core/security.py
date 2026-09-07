import hashlib
import secrets
import base64
import hmac

_ITERATIONS = 210_000

def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        _ITERATIONS,
    )

    salt_b64 = base64.b64encode(salt).decode("ascii")
    digest_b64 = base64.b64encode(digest).decode("ascii")

    return f"pbkdf2_sha256${_ITERATIONS}${salt_b64}${digest_b64}"

def verify_password(password: str, stored_hash: str) -> bool:
    try:
        algorithm, iterations, salt_b64, digest_b64 = stored_hash.split("$")
        if algorithm != "pbkdf2_sha256":
            return False

        salt = base64.b64decode(salt_b64)
        expected_digest = base64.b64decode(digest_b64)

        actual_digest = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt,
            int(iterations),
        )

        return hmac.compare_digest(actual_digest, expected_digest)
    except Exception:
        return False
    
