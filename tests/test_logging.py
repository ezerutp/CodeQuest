import logging

from codequest.app.logging_setup import RedactSecretsFilter


def test_redacts_api_keys_in_log_messages() -> None:
    record = logging.LogRecord("t", logging.INFO, __file__, 1, "key=%s", ("sk-ant-api03-abcdefghijklmnop",), None)

    RedactSecretsFilter().filter(record)

    assert "abcdefghijklmnop" not in record.getMessage()
    assert "[REDACTED]" in record.getMessage()
