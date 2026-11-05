from talkgenerator.util import http_util


def test_redact_hides_keys():
    message = "Max retries exceeded with url: /api/?key=SECRET123&q=cat (Caused by timeout)"
    assert "SECRET123" not in http_util.redact(message)
    assert "q=cat" in http_util.redact(message)
    assert "SECRET456" not in http_util.redact("grant_type=client_credentials&client_secret=SECRET456")


def test_describe_url_drops_query():
    assert http_util.describe_url("https://pixabay.com/api/?key=SECRET&q=cat") == "https://pixabay.com/api/"


def test_with_query_params_keeps_existing_ones():
    url = http_util.with_query_params("https://images.unsplash.com/photo-1?ixid=abc%2Fdef&ixlib=rb", w=1920)
    assert url == "https://images.unsplash.com/photo-1?ixid=abc%2Fdef&ixlib=rb&w=1920"


def test_cooldown():
    cooldown = http_util.Cooldown("Test service")
    assert not cooldown.active
    cooldown.trigger(60, "testing")
    assert cooldown.active
