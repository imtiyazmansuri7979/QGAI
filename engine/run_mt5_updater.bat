import MetaTrader5 as mt5

# Path to the specific terminal you want to use
terminal_path = r"C:\Imtiyaz\Vantage MT5 005\terminal64.exe"

# Initialize the connection
if not mt5.initialize(path=terminal_path, login=25334572, password="Imtiyaz7979@", server="VantageMarkets-Demo"):
    print("Initialize failed, error code =", mt5.last_error())
    quit()

# Your existing code (which uses your SYMBOL variable) goes here
print("Connected successfully to VantageMarkets-Demo")

# Example of how to use your symbol variable if needed:
# symbol = "XAUUSD"
# ... rest of your data logic ...

mt5.shutdown()