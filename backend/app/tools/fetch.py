import ipaddress
import socket
from urllib.parse import urlparse
import httpx
from bs4 import BeautifulSoup
from .base import FetchResult

class SafeWebFetcher:
    def __init__(self, allowed_hosts: set[str], timeout: float = 10, max_bytes: int = 2_000_000):
        self.allowed_hosts = {host.lower() for host in allowed_hosts}
        self.timeout = timeout
        self.max_bytes = max_bytes

    def validate_url(self, url: str) -> str:
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError("Only credential-free HTTP(S) URLs are allowed")
        host = parsed.hostname.lower()
        if self.allowed_hosts and host not in self.allowed_hosts:
            raise ValueError("Host is not in URL_FETCH_ALLOWED_HOSTS")
        for info in socket.getaddrinfo(host, parsed.port or (443 if parsed.scheme == "https" else 80), type=socket.SOCK_STREAM):
            address = ipaddress.ip_address(info[4][0])
            if not address.is_global:
                raise ValueError("Private, loopback, link-local, and reserved addresses are blocked")
        return host

    async def fetch_url(self, url: str) -> FetchResult:
        self.validate_url(url)
        async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=False) as client:
            async with client.stream("GET", url, headers={"User-Agent": "Storyweave/0.1"}) as response:
                response.raise_for_status()
                content_type = response.headers.get("content-type", "").lower()
                if not any(kind in content_type for kind in ("text/html", "text/plain")):
                    raise ValueError("Unsupported content type")
                content = bytearray()
                async for chunk in response.aiter_bytes():
                    content.extend(chunk)
                    if len(content) > self.max_bytes:
                        raise ValueError("Response exceeds configured size limit")
        text = bytes(content).decode(response.encoding or "utf-8", errors="replace")
        if "text/html" in content_type:
            soup = BeautifulSoup(text, "html.parser")
            for element in soup(["script", "style", "noscript"]):
                element.decompose()
            title = soup.title.get_text(" ", strip=True) if soup.title else None
            text = "\n".join(line.strip() for line in soup.get_text("\n").splitlines() if line.strip())
        else:
            title = None
        return FetchResult(url=url, title=title, text=text, provider="builtin-fetch")
