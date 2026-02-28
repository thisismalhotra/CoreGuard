"""
Shared rate limiter instance for the Core-Guard API.

Created in a standalone module so that both main.py (for exception handler
registration) and individual routers (for @limiter.limit() decorators) can
import the same Limiter without circular dependency issues.

Rate tiers:
  - Read endpoints (inventory, orders, kpis, agents, DB viewer): 60/minute
  - Simulation endpoints (chaos scenarios): 5/minute
  - Reset endpoint: 2/minute
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
