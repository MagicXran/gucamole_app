"""
Guacamole Encrypted JSON Auth 验证脚本

独立运行，不依赖 FastAPI。
验证: 加密 → POST /api/tokens → 拿 authToken 的完整流程。

用法:
    python verify_json_auth.py

前提:
    1. Guacamole 已启动且 guacamole-auth-json 已加载
    2. config/config.json 中 guacamole.json_secret_key 与 Guacamole 一致
"""

import base64
import hashlib
import hmac
import json
import sys
import time
import urllib.request
import urllib.parse
from pathlib import Path

# 尝试使用 cryptography 库，回退到纯标准库
try:
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    from cryptography.hazmat.primitives import padding as crypto_padding
    USE_CRYPTOGRAPHY = True
except ImportError:
    USE_CRYPTOGRAPHY = False
    print("[WARN] cryptography 库未安装，使用纯标准库回退方案")
    print("       建议: pip install cryptography\n")


def load_config() -> dict:
    config_path = Path(__file__).parent / "config" / "config.json"
    with open(config_path, "r", encoding="utf-8-sig") as f:
        return json.load(f)


def pkcs7_pad(data: bytes, block_size: int = 16) -> bytes:
    """PKCS7 填充（纯标准库回退用）"""
    pad_len = block_size - (len(data) % block_size)
    return data + bytes([pad_len] * pad_len)


def encrypt_json(payload: dict, key_hex: str) -> str:
    """加密 JSON payload 为 base64 字符串"""
    key = bytes.fromhex(key_hex)
    iv = b'\x00' * 16

    json_bytes = json.dumps(payload, separators=(',', ':')).encode('utf-8')
    signature = hmac.new(key, json_bytes, hashlib.sha256).digest()
    plaintext = signature + json_bytes

    if USE_CRYPTOGRAPHY:
        padder = crypto_padding.PKCS7(128).padder()
        padded = padder.update(plaintext) + padder.finalize()
        encryptor = Cipher(algorithms.AES(key), modes.CBC(iv)).encryptor()
        encrypted = encryptor.update(padded) + encryptor.finalize()
    else:
        # 纯标准库回退 (Python 3.6+ 无内置 AES)
        # 这里实际无法不用第三方库做 AES，所以给出提示
        print("[ERROR] 无法在没有 cryptography 库的情况下执行 AES 加密")
        print("        请安装: pip install cryptography")
        sys.exit(1)

    return base64.b64encode(encrypted).decode('ascii')


def main():
    print("=" * 60)
    print("  Guacamole Encrypted JSON Auth 验证")
    print("=" * 60)

    # 加载配置
    try:
        config = load_config()
    except FileNotFoundError:
        print("[ERROR] 找不到 config/config.json")
        sys.exit(1)

    guac_cfg = config["guacamole"]
    secret_key = guac_cfg["json_secret_key"]
    internal_url = guac_cfg["internal_url"].rstrip('/')

    print(f"\n[INFO] 密钥长度: {len(secret_key)} 字符 ({'OK' if len(secret_key) == 32 else 'ERROR: 需要32位'})")
    print(f"[INFO] Guacamole URL: {internal_url}")

    # 构建测试 payload
    payload = {
        "username": "verify_test_user",
        "expires": int((time.time() + 300) * 1000),  # 5分钟后过期
        "connections": {
            "VerifyConnection": {
                "protocol": "ssh",
                "parameters": {
                    "hostname": "127.0.0.1",
                    "port": "22",
                },
            },
        },
    }

    print(f"\n[INFO] JSON Payload:")
    print(json.dumps(payload, indent=2, ensure_ascii=False))

    # 加密
    encrypted_data = encrypt_json(payload, secret_key)
    print(f"\n[INFO] 加密后 Base64 (前80字符): {encrypted_data[:80]}...")
    print(f"[INFO] 加密数据长度: {len(encrypted_data)} 字符")

    # POST 到 Guacamole /api/tokens
    token_url = f"{internal_url}/api/tokens"
    print(f"\n[INFO] POST → {token_url}")

    try:
        form_data = urllib.parse.urlencode({"data": encrypted_data}).encode('ascii')
        req = urllib.request.Request(
            token_url,
            data=form_data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = resp.read().decode('utf-8')
            result = json.loads(body)
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8', errors='replace')
        print(f"\n[FAIL] HTTP {e.code}: {body}")
        print("\n可能原因:")
        print("  - 密钥不匹配（config.json 与 Docker JSON_SECRET_KEY 不一致）")
        print("  - guacamole-auth-json 扩展未加载（检查 docker logs guac_web）")
        print("  - Guacamole 未启动或端口不对")
        sys.exit(1)
    except Exception as e:
        print(f"\n[FAIL] 连接失败: {e}")
        print("\n可能原因:")
        print("  - Guacamole 未启动")
        print(f"  - URL 不可达: {token_url}")
        sys.exit(1)

    # 解析响应
    auth_token = result.get("authToken", "")
    data_source = result.get("dataSource", "")
    print(f"\n[OK] authToken: {auth_token[:40]}...")
    print(f"[OK] dataSource: {data_source}")

    # 构建连接标识符
    conn_name = "VerifyConnection"
    identifier_raw = f"{conn_name}\x00c\x00{data_source}"
    identifier = base64.b64encode(identifier_raw.encode('utf-8')).decode('ascii')
    external_url = guac_cfg["external_url"].rstrip('/')
    client_url = f"{external_url}/#/client/{identifier}?token={auth_token}"

    print(f"\n[OK] 连接标识符: {identifier}")
    print(f"[OK] 重定向 URL: {client_url}")

    print("\n" + "=" * 60)
    print("  验证通过！加密和认证流程完全正常。")
    print("=" * 60)
    print(f"\n  dataSource = \"{data_source}\"")
    print("  请记住这个值，代码中会用到。\n")


if __name__ == "__main__":
    main()
