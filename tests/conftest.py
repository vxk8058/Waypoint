import pytest

from backend.pipeline import build_all


@pytest.fixture(scope="session")
def bundles():
    return build_all()


@pytest.fixture(scope="session")
def primary(bundles):
    return next(b for b in bundles if b.profile.is_primary_demo)
