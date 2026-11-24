"""Сайты учеников: /s/<логин>/ — статические файлы прямо из папки ученика (только чтение). Папку и публикацию
задаёт преподаватель. Ничего за пределами папки сайта не отдаём: ни скрытые файлы, ни ярлыки наружу."""
import os
import re
import stat
from pathlib import Path

# сегмент пути: не с точки (никаких .ssh, .., скрытых файлов); буквы любого алфавита, цифры, пробел, . _ -
_SEGMENT = re.compile(r"^[^\W][\w .-]*$")
MAX_DIR = 200


def home_of(homes_dir: Path, seat: int) -> Path:
    """Дом ученика на сервере: том места seat<N>, внутри — /home/student песочницы."""
    return Path(homes_dir) / f"seat{seat}" / "student"


def valid_dir(d: str) -> bool:
    return 0 < len(d) <= MAX_DIR and all(_SEGMENT.match(s) for s in d.split("/"))


def suggest_dir(home: Path) -> str | None:
    """Первая по алфавиту не скрытая папка глубиной 1–2 с index.html — подсказка преподавателю."""
    if not home.is_dir():
        return None
    found = []
    for pattern in ("*/index.html", "*/*/index.html"):
        for f in home.glob(pattern):
            rel = f.parent.relative_to(home)
            if f.is_file() and not any(p.startswith(".") for p in rel.parts):
                found.append((len(rel.parts), rel.as_posix()))
    return min(found)[1] if found else None


MAX_BYTES = 5 * 1024 * 1024
CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8", ".htm": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8",
    ".js": "text/javascript; charset=utf-8", ".mjs": "text/javascript; charset=utf-8",
    ".json": "application/json", ".txt": "text/plain; charset=utf-8", ".svg": "image/svg+xml",
    ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".gif": "image/gif", ".webp": "image/webp",
    ".ico": "image/x-icon", ".woff": "font/woff", ".woff2": "font/woff2", ".ttf": "font/ttf",
}


def _inside(path: Path, root: Path) -> bool:
    return path == root or root in path.parents


def resolve(home: Path, site_dir: str, path: str) -> Path | None:
    """Файл сайта по пути из адреса или None. Ярлыки разрешаются, и итог обязан остаться внутри папки сайта
    (а сама папка — внутри дома ученика): чужие дома, .ssh и история команд не отдаются."""
    if not valid_dir(site_dir):
        return None
    parts = path.split("/")
    if parts and parts[-1] == "":
        parts = parts[:-1]  # «css/» — каталог
    if any(not p or p.startswith(".") for p in parts):
        return None
    try:
        home = home.resolve(strict=True)
        root = (home / site_dir).resolve(strict=True)
        if not _inside(root, home) or not root.is_dir():
            return None
        target = root.joinpath(*parts).resolve(strict=True)
        if target.is_dir():
            target = (target / "index.html").resolve(strict=True)
        if not _inside(target, root) or not target.is_file():
            return None
        if target.suffix.lower() not in CONTENT_TYPES or target.stat().st_size > MAX_BYTES:
            return None
    except (OSError, RuntimeError, ValueError):
        return None
    return target


def _opened_path(fd: int, fallback: Path) -> str:
    """Настоящий путь уже открытого файла: на Linux — /proc/self/fd (подмену имени после открытия не обманешь);
    где /proc нет (разработка на Windows) — realpath."""
    proc = f"/proc/self/fd/{fd}"
    return os.readlink(proc) if os.path.exists(proc) else os.path.realpath(fallback)


def read(home: Path, site_dir: str, path: str) -> tuple[bytes, str] | None:
    """Содержимое и тип файла сайта. Файл открывается один раз (без перехода по ярлыку в последнем звене), и уже
    открытый проверяется: лежит внутри папки сайта, обычный файл, не больше MAX_BYTES. Подменить файл ярлыком
    между проверкой и чтением нельзя — читаем именно проверенное."""
    target = resolve(home, site_dir, path)
    if target is None:
        return None
    try:
        root = (home.resolve(strict=True) / site_dir).resolve(strict=True)
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_BINARY", 0)
        fd = os.open(target, flags)
    except (OSError, RuntimeError, ValueError):
        return None
    try:
        real = Path(_opened_path(fd, target))
        info = os.fstat(fd)
        kind = CONTENT_TYPES.get(real.suffix.lower())
        if not _inside(real, root) or not stat.S_ISREG(info.st_mode) or info.st_size > MAX_BYTES or kind is None:
            return None
        with os.fdopen(fd, "rb", closefd=False) as f:
            data = f.read(MAX_BYTES + 1)
        return (data, kind) if len(data) <= MAX_BYTES else None
    except OSError:
        return None
    finally:
        os.close(fd)
