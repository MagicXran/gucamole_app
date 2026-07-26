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


def test_audio_input_can_be_enabled_without_audio_output():
    connection = GuacamoleCrypto.build_rdp_connection(
        name="app_2",
        hostname="rdp.example.local",
        enable_audio=False,
        enable_audio_input=True,
    )

    params = connection["app_2"]["parameters"]
    assert "enable-audio" not in params
    assert params["enable-audio-input"] == "true"
