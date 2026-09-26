#!/usr/bin/env python3
"""
Servidor local para o Dashboard do Sistema Inteligente de Controle Semafórico.

Fornece suporte completo a:
- HTTP Range Requests (RFC 7233 / RFC 9110)
- 206 Partial Content
- Header Accept-Ranges: bytes
- Content-Range para seek instantâneo em arquivos de mídia grandes (MP4)
- Threading para streaming assíncrono e não-bloqueante
- Servir arquivos estáticos do frontend e media/
"""

import datetime
import email.utils
import os
from pathlib import Path
import re
import socketserver
import sys
import urllib.parse
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

BASE_DIR = Path(__file__).resolve().parent

# Padrão para cabeçalho Range (ex: bytes=0-1024, bytes=1024-, bytes=-500)
RANGE_HEADER_REGEX = re.compile(r"^bytes=(\d*)-(\d*)$")


class RangeHTTPRequestHandler(SimpleHTTPRequestHandler):
    """
    Handler com suporte a HTTP Range / 206 Partial Content
    necessário para seek no player HTML5 em arquivos MP4.
    """

    protocol_version = "HTTP/1.1"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(BASE_DIR), **kwargs)

    def send_head(self):
        """Envia cabeçalhos HTTP com suporte a Range Requests."""
        # Redirecionamento da raiz / para /frontend/
        if self.path in ("/", ""):
            self.send_response(HTTPStatus.FOUND)
            self.send_header("Location", "/frontend/")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return None

        path = self.translate_path(self.path)
        f = None

        if os.path.isdir(path):
            parts = urllib.parse.urlsplit(self.path)
            if not parts.path.endswith(("/", "%2f", "%2F")):
                self.send_response(HTTPStatus.MOVED_PERMANENTLY)
                new_parts = (
                    parts[0],
                    parts[1],
                    parts[2] + "/",
                    parts[3],
                    parts[4],
                )
                new_url = urllib.parse.urlunsplit(new_parts)
                self.send_header("Location", new_url)
                self.send_header("Content-Length", "0")
                self.end_headers()
                return None
            for index in self.index_pages:
                index_path = os.path.join(path, index)
                if os.path.isfile(index_path):
                    path = index_path
                    break
            else:
                return self.list_directory(path)

        ctype = self.guess_type(path)
        if path.endswith("/"):
            self.send_error(HTTPStatus.NOT_FOUND, "Arquivo não encontrado")
            return None

        try:
            f = open(path, "rb")
        except OSError:
            self.send_error(HTTPStatus.NOT_FOUND, "Arquivo não encontrado")
            return None

        try:
            fs = os.fstat(f.fileno())
            file_size = fs.st_size

            # Verificação de cache If-Modified-Since
            if "If-Modified-Since" in self.headers and "If-None-Match" not in self.headers:
                try:
                    ims = email.utils.parsedate_to_datetime(self.headers["If-Modified-Since"])
                except (TypeError, IndexError, OverflowError, ValueError):
                    pass
                else:
                    if ims.tzinfo is None:
                        ims = ims.replace(tzinfo=datetime.timezone.utc)
                    if ims.tzinfo is datetime.timezone.utc:
                        last_modif = datetime.datetime.fromtimestamp(
                            fs.st_mtime, datetime.timezone.utc
                        ).replace(microsecond=0)
                        if last_modif <= ims:
                            self.send_response(HTTPStatus.NOT_MODIFIED)
                            self.end_headers()
                            f.close()
                            return None

            range_header = self.headers.get("Range")
            if range_header:
                match = RANGE_HEADER_REGEX.match(range_header.strip())
                if match:
                    raw_start, raw_end = match.groups()
                    if raw_start == "" and raw_end == "":
                        self.send_error(HTTPStatus.BAD_REQUEST, "Formato Range inválido")
                        f.close()
                        return None
                    elif raw_start == "":
                        # bytes=-suffix (últimos N bytes)
                        suffix = int(raw_end)
                        if suffix == 0:
                            start = file_size
                            end = file_size - 1
                        elif suffix > file_size:
                            start = 0
                            end = file_size - 1
                        else:
                            start = file_size - suffix
                            end = file_size - 1
                    elif raw_end == "":
                        # bytes=start-
                        start = int(raw_start)
                        end = file_size - 1
                    else:
                        start = int(raw_start)
                        end = min(int(raw_end), file_size - 1)

                    if start > end or start >= file_size or start < 0:
                        self.send_response(HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE)
                        self.send_header("Content-Range", f"bytes */{file_size}")
                        self.send_header("Content-Length", "0")
                        self.end_headers()
                        f.close()
                        return None

                    content_length = end - start + 1
                    f.seek(start)
                    self.bytes_to_send = content_length

                    self.send_response(HTTPStatus.PARTIAL_CONTENT)
                    self.send_header("Content-Type", ctype)
                    self.send_header("Content-Range", f"bytes {start}-{end}/{file_size}")
                    self.send_header("Content-Length", str(content_length))
                    self.send_header("Accept-Ranges", "bytes")
                    self.send_header("Last-Modified", self.date_time_string(fs.st_mtime))
                    self.send_header("Cache-Control", "no-cache")
                    self.end_headers()
                    return f

            # Resposta completa 200 OK anunciando suporte a Range
            self.bytes_to_send = file_size
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(file_size))
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Last-Modified", self.date_time_string(fs.st_mtime))
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            return f

        except Exception:
            f.close()
            raise

    def copyfile(self, source, outputfile):
        """Copia exatamente a quantidade de bytes solicitada pelo cliente."""
        bytes_remaining = getattr(self, "bytes_to_send", None)
        buf_size = 64 * 1024
        try:
            if bytes_remaining is not None:
                while bytes_remaining > 0:
                    read_len = min(buf_size, bytes_remaining)
                    chunk = source.read(read_len)
                    if not chunk:
                        break
                    outputfile.write(chunk)
                    bytes_remaining -= len(chunk)
            else:
                while True:
                    chunk = source.read(buf_size)
                    if not chunk:
                        break
                    outputfile.write(chunk)
        except (ConnectionResetError, BrokenPipeError, ConnectionAbortedError):
            # Desconexões normais quando o usuário salta de frame ou navega na timeline
            pass


def run_server(port=8000, host=""):
    os.chdir(BASE_DIR)
    server_address = (host, port)

    class ReusableThreadingServer(ThreadingHTTPServer):
        allow_reuse_address = True
        daemon_threads = True

    with ReusableThreadingServer(server_address, RangeHTTPRequestHandler) as httpd:
        host_display = host if host else "localhost"
        print("=" * 60)
        print("  Servidor do Dashboard Ativo")
        print(f"  URL: http://{host_display}:{port}/frontend/")
        print("  Suporte a HTTP Range / 206 Partial Content: HABILITADO")
        print("  Pressione Ctrl+C para encerrar.")
        print("=" * 60)
        sys.stdout.flush()
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nServidor encerrado pelo usuário.")


if __name__ == "__main__":
    port = 8000
    if len(sys.argv) > 1 and sys.argv[1].isdigit():
        port = int(sys.argv[1])
    run_server(port=port)
