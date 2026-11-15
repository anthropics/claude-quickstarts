import os
import socket
from http.server import HTTPServer, SimpleHTTPRequestHandler


class HTTPServerV6(HTTPServer):
    address_family = socket.AF_INET6


def run_server():
    port = int(os.environ.get("HTTP_PORT", 8080))
    if not (1 <= port <= 65535):
        raise ValueError(f"HTTP_PORT must be between 1 and 65535, got {port}")
    os.chdir(os.path.dirname(__file__) + "/static_content")
    server_address = ("::", port)
    httpd = HTTPServerV6(server_address, SimpleHTTPRequestHandler)
    print(f"Starting HTTP server on port {port}...")  # noqa: T201
    httpd.serve_forever()


if __name__ == "__main__":
    run_server()
