from db.gestione_db import save_smtp_config, get_smtp_config, get_db_connection

def test_smtp_save():
    # Simulate a family ID (assuming 1 exists, or I can find one)
    # First, let's find a valid family ID
    with get_db_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT id_famiglia FROM Famiglie LIMIT 1")
        res = cur.fetchone()
        if not res:
            print("No families found to test with.")
            return
        id_famiglia = res['id_famiglia']
        print(f"Testing with id_famiglia: {id_famiglia}")

    # Define settings
    settings = {
        'server': 'smtp.test.com',
        'port': '587',
        'user': 'test_user',
        'password': 'test_password_123',
        'provider': 'custom'
    }

    # Save settings
    print(f"Saving settings: {settings}")
    success = save_smtp_config(settings, id_famiglia)
    if success:
        print("Save successful.")
    else:
        print("Save failed.")

    # Retrieve settings
    saved_settings = get_smtp_config(id_famiglia)
    print(f"Retrieved settings: {saved_settings}")

    # Verify password
    if saved_settings['password'] == 'test_password_123':
        print("SUCCESS: Password saved correctly.")
    else:
        print(f"FAILURE: Password mismatch. Expected 'test_password_123', got '{saved_settings.get('password')}'")

if __name__ == "__main__":
    test_smtp_save()
