from db.gestione_db import get_db_connection

def add_family_key_columns():
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            
            # Add column to Appartenenza_Famiglia
            print("Adding chiave_famiglia_criptata to Appartenenza_Famiglia...")
            try:
                cur.execute("ALTER TABLE Appartenenza_Famiglia ADD COLUMN chiave_famiglia_criptata TEXT")
            except Exception as e:
                print(f"Column might already exist in Appartenenza_Famiglia: {e}")
                con.rollback()
            else:
                con.commit()

            # Add column to Inviti
            print("Adding chiave_famiglia_criptata to Inviti...")
            try:
                cur.execute("ALTER TABLE Inviti ADD COLUMN chiave_famiglia_criptata TEXT")
            except Exception as e:
                print(f"Column might already exist in Inviti: {e}")
                con.rollback()
            else:
                con.commit()
                
            print("Migration completed.")

    except Exception as e:
        print(f"Error during migration: {e}")

if __name__ == "__main__":
    add_family_key_columns()
