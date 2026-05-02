from __future__ import annotations

import time
from dataclasses import dataclass, field
from urllib.parse import urlencode

import requests


BASE_URL = "https://renati.sunedu.gob.pe"


@dataclass(slots=True)
class RenatiClient:
    base_url: str = BASE_URL
    timeout: int = 30
    retries: int = 3
    pause_seconds: float = 0.6
    session: requests.Session = field(init=False)

    def __post_init__(self) -> None:
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Referer": f"{self.base_url}/busqueda",
            }
        )

    def build_search_url(self, query: str, start: int = 0, rpp: int = 100) -> str:
        params = {"q": query}
        if start:
            params["start"] = start
        if rpp:
            params["rpp"] = rpp
        return f"{self.base_url}/busqueda/simple/data?{urlencode(params)}"

    def fetch_search_page(self, query: str, start: int = 0, rpp: int = 100) -> str:
        url = self.build_search_url(query=query, start=start, rpp=rpp)
        return self.get_text(url)

    def get_text(self, url: str) -> str:
        last_error: Exception | None = None
        for attempt in range(1, self.retries + 1):
            try:
                response = self.session.get(url, timeout=self.timeout)
                response.raise_for_status()
                if _looks_like_antibot(response.text):
                    raise RuntimeError(
                        "RENATI devolvio una pagina anti-bot (Anubis). "
                        "Usa --source csv o ejecuta un flujo con navegador en el siguiente sprint."
                    )
                if attempt > 1:
                    time.sleep(self.pause_seconds)
                return response.text
            except RuntimeError:
                raise
            except requests.RequestException as exc:
                last_error = exc
                time.sleep(self.pause_seconds * attempt)
        raise RuntimeError(f"No se pudo descargar {url}: {last_error}") from last_error


def _looks_like_antibot(html: str) -> bool:
    sample = html[:5000].lower()
    return "making sure you" in sample and "not a bot" in sample or "anubis_challenge" in sample
