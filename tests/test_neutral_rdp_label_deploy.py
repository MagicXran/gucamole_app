from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_guacamole_images_are_pinned_to_matching_1_6_0_versions():
    compose = (REPO_ROOT / "deploy" / "docker-compose.yml").read_text(encoding="utf-8")
    guac_web_dockerfile = (REPO_ROOT / "deploy" / "guac-web.Dockerfile").read_bytes()

    assert "dockerfile: deploy/guacd-utf8-rdpdr.Dockerfile" in compose
    assert "image: nercar-portal-guacd:1.6.0-user-space" in compose
    assert b"FROM guacamole/guacamole:1.6.0" in guac_web_dockerfile
    assert not guac_web_dockerfile.startswith(b"\xef\xbb\xbf")


def test_guacd_uses_pinned_utf8_rdpdr_patch_image():
    dockerfile = (REPO_ROOT / "deploy" / "guacd-utf8-rdpdr.Dockerfile").read_text(
        encoding="utf-8"
    )

    assert "FROM guacamole/guacd:1.6.0 AS guacd-source" in dockerfile
    assert "patch-guacd-rdpdr-drive-name.py" in dockerfile
    assert "GUACD_RDP_LIBRARY_SHA256=00e12f90104aaa8cffc0b0b8ab461ff1f774e7b2c45c47b978e3b7e2d088e729" in dockerfile


def test_compose_passes_user_space_label_overrides_to_backend():
    compose = (REPO_ROOT / "deploy" / "docker-compose.yml").read_text(encoding="utf-8")

    assert "GUACAMOLE_CLIENT_NAME: ${GUACAMOLE_CLIENT_NAME:-用户空间}" in compose
    assert "GUACAMOLE_DRIVE_NAME: ${GUACAMOLE_DRIVE_NAME:-用户空间}" in compose


def test_neutral_label_migration_only_resets_automatic_directories_and_tokens():
    migration = (REPO_ROOT / "database" / "migrate_neutral_rdp_labels.sql").read_text(
        encoding="utf-8"
    )

    assert "UPDATE remote_app" in migration
    assert "remote_app_dir = NULL" in migration
    assert r"\\\\tsclient\\GuacDrive" in migration
    assert r"\\\\tsclient\\用户数据目录" in migration
    assert r"\\\\tsclient\\UserFiles" in migration
    assert r"\\\\tsclient\\用户空间" in migration
    assert "DELETE FROM token_cache" in migration
    assert "UPDATE portal_user" not in migration
    assert "UPDATE remote_app_acl" not in migration
