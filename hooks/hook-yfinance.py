from PyInstaller.utils.hooks import collect_all

# Force collection of everything related to yfinance
datas, binaries, hiddenimports = collect_all('yfinance')
