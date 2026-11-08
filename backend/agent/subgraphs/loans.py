"""Standalone Loans branch for recorded student and auto loan balances."""
from ...services.profile_service import ProfileService
from .account import build_account_graph


def build_loans_graph(profiles: ProfileService, worker=None):
    return build_account_graph(profiles, "loans", worker)
