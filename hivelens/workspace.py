"""Request-local workspaces; demo preserves existing data, production starts separately."""
from contextlib import contextmanager
from contextvars import ContextVar
from . import config

_current = ContextVar('hivelens_workspace', default='demo')
MODES = ('demo', 'production')


def current() -> str:
    return _current.get()


@contextmanager
def scope(mode: str):
    if mode not in MODES:
        raise ValueError('Choose demo or production workspace.')
    token = _current.set(mode)
    try:
        yield
    finally:
        _current.reset(token)


def data_dir():
    return config.DATA_DIR if current() == 'demo' else config.DATA_DIR / 'workspaces' / 'production'


def hives_dir():
    return config.HIVES_DIR if current() == 'demo' else data_dir() / 'hives'
