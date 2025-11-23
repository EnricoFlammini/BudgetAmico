
def test_suffix_logic(ticker, conto_selezionato):
    print(f"Testing with ticker='{ticker}' and conto={conto_selezionato}")
    
    original_ticker = ticker
    
    if conto_selezionato and 'borsa_default' in conto_selezionato and conto_selezionato['borsa_default']:
        suffix = conto_selezionato['borsa_default']
        if "." not in ticker:
            ticker += suffix
            
    print(f"Result: '{ticker}'")
    return ticker

# Test Cases
print("--- Test Case 1: Suffix added ---")
assert test_suffix_logic("AAPL", {'borsa_default': '.MI'}) == "AAPL.MI"

print("\n--- Test Case 2: Suffix NOT added (already has suffix) ---")
assert test_suffix_logic("AAPL.US", {'borsa_default': '.MI'}) == "AAPL.US"

print("\n--- Test Case 3: Suffix NOT added (no default exchange) ---")
assert test_suffix_logic("AAPL", {'borsa_default': ''}) == "AAPL"

print("\n--- Test Case 4: Suffix NOT added (None account) ---")
assert test_suffix_logic("AAPL", None) == "AAPL"

print("\nAll tests passed!")
