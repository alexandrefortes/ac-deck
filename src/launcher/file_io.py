"""Mecanismos de arquivos compartilhados pelo launcher e pelas ferramentas.

Usa apenas a biblioteca padrão. Políticas de diretórios, schemas, locks,
backups e recuperação de transações pertencem aos respectivos consumidores.
Leitores de arquivos regulares e de referências exclusivas mantêm contratos
distintos; a leitura JSON abaixo aceita somente objetos, sem validar schemas.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path, PureWindowsPath
import stat


REPARSE_POINT = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)


class SafetyError(RuntimeError):
    """Uma condição impede leitura ou cópia verificável."""


def absolute(path: str | Path) -> Path:
    if ".." in Path(path).parts:
        raise SafetyError(f"Traversal proibido: {path}")
    return Path(os.path.abspath(os.fspath(path)))


def linked(info: os.stat_result) -> bool:
    return stat.S_ISLNK(info.st_mode) or bool(
        getattr(info, "st_file_attributes", 0) & REPARSE_POINT
    )


def check_components(path: Path) -> None:
    """Não resolve links: verifica cada componente existente do caminho."""
    current = Path(path.anchor)
    for component in path.parts[1:]:
        current /= component
        try:
            info = current.lstat()
        except FileNotFoundError:
            continue
        if linked(info):
            raise SafetyError(f"Link ou reparse point proibido: {current}")


def inside(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def source_root(path: str | Path) -> Path:
    source = absolute(path)
    check_components(source)
    if not source.is_dir():
        raise SafetyError(f"Origem não é um diretório existente: {source}")
    return source


def relative_file(value: object) -> str:
    if not isinstance(value, str) or not value or "\x00" in value:
        raise SafetyError("Caminho relativo de arquivo inválido")
    windows = PureWindowsPath(value)
    normalized = value.replace("\\", "/")
    parts = normalized.split("/")
    if (windows.drive or windows.root or normalized.startswith("/")
            or ":" in value or any(part in ("", ".", "..") for part in parts)):
        raise SafetyError(f"Caminho absoluto, traversal ou alias proibido: {value!r}")
    # Windows removes trailing dots/spaces and reserves device names, even with
    # extensions. Deny these forms on every host so a manifest stays portable.
    devices = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(10)),
               *(f"LPT{i}" for i in range(10))}
    if any(part.endswith((".", " ")) or part.split(".")[0].upper() in devices
           or any(char in part for char in '<>"|?*') for part in parts):
        raise SafetyError(f"Nome de arquivo não portátil: {value!r}")
    return normalized


def signature(info: os.stat_result) -> tuple[int, int, int, int]:
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns


def open_regular(path: Path):
    check_components(path)
    before = path.lstat()
    if linked(before) or not stat.S_ISREG(before.st_mode):
        raise SafetyError(f"Origem deve ser arquivo regular sem link: {path}")
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags)
    try:
        opened = os.fstat(descriptor)
        if linked(opened) or not stat.S_ISREG(opened.st_mode):
            raise SafetyError(f"Origem aberta não é arquivo regular: {path}")
        if signature(before) != signature(opened):
            raise SafetyError(f"Origem mudou durante a abertura: {path}")
        return os.fdopen(descriptor, "rb"), opened
    except BaseException:
        os.close(descriptor)
        raise


def hash_file(path: Path) -> tuple[str, os.stat_result]:
    stream, before = open_regular(path)
    digest = hashlib.sha256()
    with stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
        after = os.fstat(stream.fileno())
    check_components(path)
    if signature(before) != signature(after) or signature(before) != signature(path.lstat()):
        raise SafetyError(f"Origem mudou durante o hash: {path}")
    return digest.hexdigest(), before


def require_reference(info: os.stat_result, path: Path) -> None:
    """Referências exigem arquivo regular com exatamente um vínculo observado.

    A regra fica separada dos leitores genéricos de código e relatórios locais.
    """
    if linked(info) or not stat.S_ISREG(info.st_mode):
        raise SafetyError(f"Referência deve ser arquivo regular sem link: {path}")
    if info.st_nlink != 1:
        raise SafetyError(f"Referência exige nlink=1; observado nlink={info.st_nlink}: {path}")


def open_reference(path: Path):
    check_components(path)
    before = path.lstat()
    require_reference(before, path)
    stream, opened = open_regular(path)
    try:
        require_reference(opened, path)
        check_components(path)
        current = path.lstat()
        require_reference(current, path)
        if signature(before) != signature(opened) or signature(before) != signature(current):
            raise SafetyError(f"Referência mudou durante a abertura: {path}")
        return stream, opened
    except BaseException:
        stream.close()
        raise


def hash_reference_file(path: Path) -> tuple[str, os.stat_result]:
    """Hash estrito de referência; não muda a política de hash_file genérico."""
    stream, before = open_reference(path)
    digest = hashlib.sha256()
    with stream:
        while block := stream.read(1024 * 1024):
            digest.update(block)
        after = os.fstat(stream.fileno())
    check_components(path)
    current = path.lstat()
    require_reference(after, path)
    require_reference(current, path)
    if signature(before) != signature(after) or signature(before) != signature(current):
        raise SafetyError(f"Referência mudou durante o hash: {path}")
    return digest.hexdigest(), before


def write_json(path: Path, payload: dict) -> None:
    """Valida componentes sem links e cria JSON novo, sem substituir arquivos."""
    check_components(path)
    write_new_json(path, payload)


def write_new_json(path: Path, payload: dict) -> None:
    """Serializa em arquivo novo, sem validar componentes do caminho.

    Preserva o contrato das gravações de preparo de pacote: o consumidor define
    as verificações de diretório, locks e transações antes desta criação.
    """
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(payload, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def read_document(path: str | Path) -> tuple[dict, str]:
    path = absolute(path)
    stream, before = open_regular(path)
    with stream:
        content = stream.read()
        after = os.fstat(stream.fileno())
    check_components(path)
    if signature(before) != signature(after) or signature(before) != signature(path.lstat()):
        raise SafetyError(f"Documento mudou durante a leitura: {path}")
    payload = json.loads(content.decode("utf-8"))
    if not isinstance(payload, dict):
        raise SafetyError("JSON deve conter um objeto")
    return payload, hashlib.sha256(content).hexdigest()


def read_json(path: str | Path) -> dict:
    return read_document(path)[0]


def copy_verified(source: Path, destination: Path, expected_hash: str) -> str:
    """Cópia por bytes, exclusiva: não cria hardlink nem preserva permissões."""
    check_components(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    check_components(destination)
    stream, before = open_reference(source)
    digest = hashlib.sha256()
    with stream, destination.open("xb") as target:
        target_before = os.fstat(target.fileno())
        require_reference(target_before, destination)
        while block := stream.read(1024 * 1024):
            target.write(block)
            digest.update(block)
        after = os.fstat(stream.fileno())
        target.flush()
        target_after = os.fstat(target.fileno())
        require_reference(after, source)
        require_reference(target_after, destination)
        if signature(target_before)[:2] != signature(target_after)[:2]:
            raise SafetyError(f"Identidade da cópia mudou: {destination}")
    check_components(source)
    current_source = source.lstat()
    require_reference(current_source, source)
    if (signature(before) != signature(after)
            or signature(before) != signature(current_source) or digest.hexdigest() != expected_hash):
        raise SafetyError(f"Origem mudou durante a cópia: {source}")
    copied_hash, copied_info = hash_reference_file(destination)
    if signature(target_after) != signature(copied_info):
        raise SafetyError(f"Cópia mudou durante a conferência: {destination}")
    if copied_hash != expected_hash:
        raise SafetyError(f"Hash da cópia diverge: {destination}")
    return copied_hash
