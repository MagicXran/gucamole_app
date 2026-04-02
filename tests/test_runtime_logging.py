import io
import importlib
import json
import logging
import subprocess
import sys
from pathlib import Path

import backend


def test_structured_formatter_includes_instance_identity_and_event_fields():
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(
        backend.StructuredLogFormatter(
            instance_id="portal-test",
            service_name="portal-backend",
        )
    )

    logger = logging.getLogger("tests.runtime_logging")
    logger.handlers = [handler]
    logger.setLevel(logging.INFO)
    logger.propagate = False

    logger.info(
        "startup complete",
        extra=backend.log_extra(
            "portal_startup",
            cleanup_interval_seconds=60,
            upload_cleanup_interval_seconds=3600,
        ),
    )

    payload = json.loads(stream.getvalue())
    assert payload["instance_id"] == "portal-test"
    assert payload["service_name"] == "portal-backend"
    assert payload["event"] == "portal_startup"
    assert payload["message"] == "startup complete"
    assert payload["cleanup_interval_seconds"] == 60
    assert payload["upload_cleanup_interval_seconds"] == 3600


def test_structured_formatter_falls_back_to_default_event_for_plain_logs():
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(
        backend.StructuredLogFormatter(
            instance_id="portal-test",
            service_name="portal-backend",
        )
    )

    logger = logging.getLogger("tests.runtime_logging.plain")
    logger.handlers = [handler]
    logger.setLevel(logging.INFO)
    logger.propagate = False

    logger.info("plain log line")

    payload = json.loads(stream.getvalue())
    assert payload["instance_id"] == "portal-test"
    assert payload["service_name"] == "portal-backend"
    assert payload["event"] == "log"
    assert payload["message"] == "plain log line"


def test_configure_logging_preserves_existing_root_handlers_by_default():
    root = logging.getLogger()
    original_handlers = list(root.handlers)
    original_level = root.level
    sentinel_stream = io.StringIO()
    sentinel_handler = logging.StreamHandler(sentinel_stream)

    try:
        root.handlers = [sentinel_handler]
        backend.configure_logging(logging.INFO)
        assert root.handlers == [sentinel_handler]
    finally:
        root.handlers = original_handlers
        root.setLevel(original_level)


def test_importing_backend_app_does_not_clobber_existing_root_handlers():
    root = logging.getLogger()
    original_handlers = list(root.handlers)
    original_level = root.level
    sentinel_stream = io.StringIO()
    sentinel_handler = logging.StreamHandler(sentinel_stream)

    try:
        root.handlers = [sentinel_handler]
        sys.modules.pop("backend.app", None)
        importlib.import_module("backend.app")
        assert root.handlers == [sentinel_handler]
    finally:
        root.handlers = original_handlers
        root.setLevel(original_level)
        sys.modules.pop("backend.app", None)


def test_importing_backend_app_does_not_emit_python_multipart_deprecation_warning():
    repo_root = Path(__file__).resolve().parent.parent
    result = subprocess.run(
        [sys.executable, "-W", "always", "-c", "import backend.app"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )

    combined = f"{result.stdout}\n{result.stderr}"
    assert result.returncode == 0, combined
    assert "Please use `import python_multipart` instead." not in combined
