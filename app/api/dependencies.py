"""FastAPI dependencies shared by route modules."""

from __future__ import annotations

from functools import lru_cache

from fastapi import Depends

from app.core.config import Settings, get_settings
from app.repositories.memory import create_memory_repositories
from app.repositories.protocols import RepositoryBundle
from app.repositories.supabase import create_supabase_repositories


@lru_cache
def _repository_bundle(enable_mock_data: bool) -> RepositoryBundle:
    if enable_mock_data:
        return create_memory_repositories()
    return create_supabase_repositories()


def get_repository_bundle(settings: Settings = Depends(get_settings)) -> RepositoryBundle:
    return _repository_bundle(settings.enable_mock_data)


def reset_repository_bundle_cache() -> None:
    _repository_bundle.cache_clear()
