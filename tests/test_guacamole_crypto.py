from backend.guacamole_crypto import GuacamoleCrypto


def test_build_rdp_connection_sets_transfer_disable_flags():
    connection = GuacamoleCrypto.build_rdp_connection(
        name="app_1",
        hostname="rdp.example.local",
        enable_drive=True,
        drive_path="/drive/portal_u1",
        disable_download=True,
        disable_upload=True,
    )

    params = connection["app_1"]["parameters"]
    assert params["enable-drive"] == "true"
    assert params["disable-download"] == "true"
    assert params["disable-upload"] == "true"
