"""daily-log-parser: a general-purpose, file-driven CLI plan tracker.

All plan data (tasks, day-types, festivals, timetables) lives in a single
JSON file. This package is a pure handler: it reads the file, modifies it,
saves it. No plan data is hardcoded in Python.
"""

__version__ = "1.1.0"
