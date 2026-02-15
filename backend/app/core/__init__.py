from __future__ import annotations

__all__ = ['scan_files', 'train_model', 'get_importance']


def __getattr__(name: str):
    if name in __all__:
        from backend.app.core import ml

        return getattr(ml, name)
    raise AttributeError(f'module {__name__!r} has no attribute {name!r}')
