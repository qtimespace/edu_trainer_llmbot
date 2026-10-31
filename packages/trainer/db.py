from functools import lru_cache

from sqlalchemy import Engine, create_engine


def make_engine(url: str) -> Engine:
    # без таймаута подключение к недоступной БД висит минутами — и вместе с ним запрос API
    return create_engine(url, pool_pre_ping=True, connect_args={"connect_timeout": 10})


@lru_cache
def get_engine(url: str) -> Engine:
    return make_engine(url)
