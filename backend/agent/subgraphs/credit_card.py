"""Standalone Credit Card branch."""
from ...services.profile_service import ProfileService
from .account import build_account_graph


def build_credit_card_graph(profiles: ProfileService, worker=None):
    return build_account_graph(profiles, "credit_card", worker)
