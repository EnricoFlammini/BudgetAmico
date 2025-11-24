import sys
from cx_Freeze import setup, Executable

# Dependencies are automatically detected, but it might need fine tuning.
build_exe_options = {
    "packages": [
        "flet",
        "flet_desktop",
        "flet_core",
        "flet_runtime",
        "google.auth",
        "google.oauth2",
        "googleapiclient",
        "pandas",
        "openpyxl",
        "numpy",
        "yfinance",
        "curl_cffi",
        "requests",
        "dateutil",
        "pytz",
        "asyncio",
        "threading",
    ],
    "includes": [
        "app_controller",
        "google_auth_manager",
        "google_drive_manager",
    ],
    "include_files": [
        ("assets", "assets"),
        ("credentials.json", "credentials.json"),
    ],
    "excludes": ["tkinter", "unittest", "test"],
}

# GUI applications require a different base on Windows
base = None  # cx_Freeze will auto-detect

setup(
    name="Budget Amico",
    version="1.0",
    description="Budget Amico - Gestione Budget Familiare",
    options={"build_exe": build_exe_options},
    executables=[
        Executable(
            "main.py",
            base=base,
            target_name="Budget Amico.exe",
            icon="assets/icon.ico",
        ),
        # Console version for debugging
        Executable(
            "main.py",
            base=None,  # Console mode
            target_name="Budget Amico Console.exe",
            icon="assets/icon.ico",
        )
    ],
)
