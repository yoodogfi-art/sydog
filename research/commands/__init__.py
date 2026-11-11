"""
research/commands/  —  one file per kind of research command.

Each module exposes a function  run(command, instrument, args) -> reply  where
reply is either a text string or a (png_bytes, caption) tuple. To add a new
kind of command, add a module here and register it in research/registry.py.
"""
