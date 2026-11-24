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
