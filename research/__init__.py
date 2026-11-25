"""
research/  —  the research engine: data -> numbers -> a reply.

Surface-agnostic by design. registry.py lists the command kinds, commands/ holds
one module per kind, and telegram_handlers.py is the only module that knows
Telegram exists.
"""
