"""The Campus Customs agent team: Boss, Inventory, Accounting, Facilities, and Customer Service."""

from . import accounting, boss, customer_service, facilities, inventory
from .base import AgentSpec, Team

ALL_SPECS: list[AgentSpec] = [boss.SPEC, inventory.SPEC, accounting.SPEC, facilities.SPEC, customer_service.SPEC]


def build_team(**kwargs) -> Team:
    return Team(ALL_SPECS, **kwargs)
