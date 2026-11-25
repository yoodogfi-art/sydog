"""
ingestion/  —  how source data gets refreshed and turned into processed CSVs.

base.py defines the provider interface, registry.py maps providers to updaters,
processor.py turns raw Excel into canonical CSVs. Callers use refresh_all /
refresh_one / process_excel_data and never learn a provider's mechanism.
"""
