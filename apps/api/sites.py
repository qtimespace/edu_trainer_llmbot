"""Сайты учеников: /s/<логин>/ — без входа, только статика из опубликованной папки. Страницы живут на домене
панели, поэтому каждый ответ — с CSP sandbox: у страницы «чужое» происхождение, сессия преподавателя ей недоступна."""
from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, Response
from sqlalchemy import Engine

from apps.api.auth import account_dep
from apps.api.deps import engine_dep, settings_dep
from apps.api.group import site_url
from trainer import sites
from trainer.classroom.groups import GroupStore
from trainer.settings import Settings

router = APIRouter()

HEADERS = {"Content-Security-Policy": "sandbox allow-scripts allow-forms allow-popups allow-modals",
           "X-Content-Type-Options": "nosniff", "Cache-Control": "no-cache"}
NOT_FOUND = """<!doctype html><meta charset="utf-8"><title>Сайт не найден</title>
<body style="font-family:sans-serif;text-align:center;margin-top:20vh"><h1>Здесь пока пусто</h1>
<p>Сайт ещё не опубликован или такой страницы нет.</p></body>"""


def _not_found() -> Response:
    return HTMLResponse(NOT_FOUND, status_code=404, headers=HEADERS)


@router.get("/s/{login}", include_in_schema=False)
def site_root(login: str) -> Response:
    return RedirectResponse(f"/s/{login}/", status_code=307, headers=HEADERS)


@router.get("/s/{login}/{path:path}", include_in_schema=False)
def site_file(login: str, path: str, engine: Engine = Depends(engine_dep),
              settings: Settings = Depends(settings_dep)) -> Response:
    student = GroupStore(engine).student_by_login(login)
    if student is None or not student.site_published or not student.site_dir:
        return _not_found()
    target = sites.resolve(sites.home_of(settings.homes_dir, student.seat), student.site_dir, path)
    if target is None:
        return _not_found()
    return FileResponse(target, media_type=sites.CONTENT_TYPES[target.suffix.lower()], headers=HEADERS)


@router.get("/me/site")
def my_site(who=Depends(account_dep), engine: Engine = Depends(engine_dep),
            settings: Settings = Depends(settings_dep)) -> dict:
    student = GroupStore(engine).student(who[0].id)
    if student is None or not student.site_published or not student.site_dir:
        return {"url": None}
    return {"url": site_url(settings, student.login)}
