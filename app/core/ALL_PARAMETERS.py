"""
ALL_PARAMETERS.py - Single Source of Truth (SSoT) Alias

CLIENT SPECIFICATION: The document references ALL_PARAMETERS.py as the SSoT.
This file provides an alias to strict_config.py for consistency between
documentation and code.

All parameters should be accessed through STRICT_CONFIG imported from this module.
"""

from .strict_config import STRICT_CONFIG, StrictSettings, load_strict_config, reload_strict_config

# Export the main configuration
__all__ = [
    "STRICT_CONFIG",
    "StrictSettings",
    "load_strict_config",
    "reload_strict_config"
]

# Document that this is an alias
# The actual implementation is in strict_config.py
# This file exists to match the CLIENT SPECIFICATION documentation

