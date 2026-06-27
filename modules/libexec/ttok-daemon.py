from __future__ import annotations

import select
import socket
import sys
import time
from pathlib import Path
from urllib.parse import unquote, urlparse

import tiktoken

TOKENIZER = "o200k_base"
MAX_CLIPBOARD_PATHS = 100
IDLE_TIMEOUT_SECONDS = 600


def count_tokens(text: str) -> int:
    return len(ENCODING.encode(text, disallowed_special=()))


def count_file(path: Path) -> int:
    return count_tokens(path.read_text(errors="replace"))


def resolve_path(path: Path, base_dir: Path) -> Path:
    if path.is_absolute():
        return path
    return base_dir / path


def path_from_clipboard_line(line: str, base_dir: Path) -> Path:
    if line.startswith("file://"):
        return Path(unquote(urlparse(line).path))
    return resolve_path(Path(line).expanduser(), base_dir)


def paths_from_clipboard_text(text: str, base_dir: Path) -> list[Path] | None:
    lines = [line.strip() for line in text.strip().splitlines() if line.strip()]
    if not lines or len(lines) > MAX_CLIPBOARD_PATHS:
        return None

    paths = [path_from_clipboard_line(line, base_dir) for line in lines]
    if all(path.is_file() for path in paths):
        return paths
    return None


def count_request(args: list[str], input_bytes: bytes, base_dir: Path) -> int:
    if args:
        paths = [resolve_path(Path(arg).expanduser(), base_dir) for arg in args]
        if all(path.is_file() for path in paths):
            return sum(count_file(path) for path in paths)
        return count_tokens(" ".join(args))

    text = input_bytes.decode(errors="replace")
    if paths := paths_from_clipboard_text(text, base_dir):
        return sum(count_file(path) for path in paths)
    return count_tokens(text)


def read_c_string(data: bytes, offset: int) -> tuple[str, int]:
    end = data.find(b"\0", offset)
    if end < 0:
        raise ValueError("malformed request")
    return data[offset:end].decode(errors="surrogateescape"), end + 1


def parse_request(data: bytes) -> tuple[Path, list[str], bytes]:
    prefix_v2 = b"TTOK2\0"
    prefix_v1 = b"TTOK1\0"
    if data.startswith(prefix_v2):
        caller_dir, offset = read_c_string(data, len(prefix_v2))
        base_dir = Path(caller_dir)
    elif data.startswith(prefix_v1):
        offset = len(prefix_v1)
        base_dir = Path.cwd()
    else:
        raise ValueError("unknown request")

    argc_text, offset = read_c_string(data, offset)
    argc = int(argc_text)
    args: list[str] = []
    for _ in range(argc):
        arg, offset = read_c_string(data, offset)
        args.append(arg)

    return base_dir, args, data[offset:]


def handle_request(data: bytes) -> bytes:
    if data == b"PING\0":
        return b"OK\n"

    base_dir, args, input_bytes = parse_request(data)
    count = count_request(args, input_bytes, base_dir)
    return f"OK\t{count}\n".encode()


def read_all(conn: socket.socket) -> bytes:
    chunks: list[bytes] = []
    while chunk := conn.recv(1024 * 1024):
        chunks.append(chunk)
    return b"".join(chunks)


def read_field(reader) -> bytes:
    chunks: list[bytes] = []
    while True:
        byte = reader.read(1)
        if not byte:
            raise ValueError("truncated request")
        if byte == b"\0":
            return b"".join(chunks)
        chunks.append(byte)


def read_exact(reader, size: int) -> bytes:
    chunks: list[bytes] = []
    remaining = size
    while remaining:
        chunk = reader.read(remaining)
        if not chunk:
            raise ValueError("truncated input")
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def handle_connection(conn: socket.socket) -> bytes:
    reader = conn.makefile("rb", buffering=0)
    magic = read_field(reader)
    if magic == b"PING":
        return b"OK\n"

    if magic == b"TTOK3":
        caller_dir = read_field(reader).decode(errors="surrogateescape")
        argc = int(read_field(reader))
        args = [read_field(reader).decode(errors="surrogateescape") for _ in range(argc)]
        input_len = int(read_field(reader))
        input_bytes = read_exact(reader, input_len)
        count = count_request(args, input_bytes, Path(caller_dir))
        return f"OK\t{count}\n".encode()

    return handle_request(magic + b"\0" + reader.read())


def serve(socket_path: str) -> None:
    socket_file = Path(socket_path)
    socket_file.parent.mkdir(parents=True, exist_ok=True)
    try:
        socket_file.unlink()
    except FileNotFoundError:
        pass

    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(socket_path)
    server.listen(16)

    try:
        last_activity = time.monotonic()
        while True:
            idle_left = IDLE_TIMEOUT_SECONDS - (time.monotonic() - last_activity)
            if idle_left <= 0:
                return
            readable, _, _ = select.select([server], [], [], idle_left)
            if not readable:
                return

            conn, _ = server.accept()
            last_activity = time.monotonic()
            with conn:
                try:
                    conn.sendall(handle_connection(conn))
                except Exception as exc:  # noqa: BLE001 - keep CLI diagnostics parseable.
                    message = str(exc).replace("\n", " ")
                    conn.sendall(f"ERR\t{message}\n".encode())
    finally:
        server.close()
        try:
            socket_file.unlink()
        except FileNotFoundError:
            pass


ENCODING = tiktoken.get_encoding(TOKENIZER)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: ttok-daemon.py SOCKET_PATH", file=sys.stderr)
        sys.exit(2)
    serve(sys.argv[1])
