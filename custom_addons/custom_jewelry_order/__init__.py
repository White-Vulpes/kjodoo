import secrets

from . import models
from . import controllers

from .controllers.api import API_KEY_PARAM


def _provision_api_key(env):
    """Generate a random API key for the order-stats endpoint on install,
    unless one has already been set (so upgrades never rotate it)."""
    params = env['ir.config_parameter'].sudo()
    if not params.get_param(API_KEY_PARAM):
        params.set_param(API_KEY_PARAM, secrets.token_urlsafe(32))