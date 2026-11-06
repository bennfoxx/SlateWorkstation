"""Media ingest engine (read-only scanner, camera reports).

Safety rule for the whole package: source media is only ever opened for reading.
No module here may delete, move or rename anything; all writes go through
safefs, which only creates *new* files outside every source root.
tests/test_ingest.py enforces this statically and against a read-only disk image.
"""
