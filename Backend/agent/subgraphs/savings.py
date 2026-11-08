"""Standalone Savings branch."""
from ...services.profile_service import ProfileService
from .account import build_account_graph


def build_savings_graph(profiles: ProfileService, worker=None):
    return build_account_graph(profiles, "savings", worker)
