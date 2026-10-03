"""Unit tests must not inherit the developer's live persistence configuration.

Storage/worker tests explicitly supply isolated SQLite stores or mocked cloud
transports. Set the safe default before test modules import the application.
"""
import os

os.environ["DAISY_PERSISTENCE"] = "memory"
os.environ["DAISY_ENV"] = "development"
