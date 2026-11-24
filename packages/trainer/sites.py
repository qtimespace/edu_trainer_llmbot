"""Сайты учеников: /s/<логин>/ — статические файлы прямо из папки ученика (только чтение). Папку и публикацию
задаёт преподаватель. Ничего за пределами папки сайта не отдаём: ни скрытые файлы, ни ярлыки наружу."""
import re
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
