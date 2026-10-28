"""Self-hosted UI fonts (#49)."""

# Third Party
import httpx

# Project
from hyperglass.frontend import self_host_fonts, google_font_url

CSS = """@font-face {
  font-family: 'Nunito';
  src: url(https://fonts.gstatic.com/s/nunito/v26/abc.woff2) format('woff2');
}"""


def _client(handler):
    original = httpx.Client

    def client(**kwargs):
        return original(transport=httpx.MockTransport(handler), **kwargs)

    return client


def test_google_font_url():
    assert google_font_url("Fira Code") == (
        "https://fonts.googleapis.com/css?family=Fira+Code:300,400,700&display=swap"
    )


def test_self_host_fonts(monkeypatch, tmp_path):
    def handler(request):
        if request.url.host == "fonts.googleapis.com":
            return httpx.Response(200, text=CSS)
        return httpx.Response(200, content=b"woff2")

    monkeypatch.setattr(httpx, "Client", _client(handler))

    assert self_host_fonts({"body": "Nunito", "mono": "Fira Code"}, tmp_path)

    font_dir = tmp_path / "public" / "fonts"
    css = (font_dir / "body.css").read_text()
    assert "fonts.gstatic.com" not in css
    name = css.split("url(/fonts/")[1].split(")")[0]
    assert (font_dir / name).read_bytes() == b"woff2"
    assert (font_dir / "mono.css").exists()


def test_self_host_fonts_falls_back(monkeypatch, tmp_path):
    monkeypatch.setattr(httpx, "Client", _client(lambda request: httpx.Response(503)))

    assert not self_host_fonts({"body": "Nunito"}, tmp_path)
    assert not (tmp_path / "public" / "fonts").exists()
