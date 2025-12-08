from db.gestione_db import get_db_connection

def migrate_db():
    try:
        with get_db_connection() as con:
            cur = con.cursor()
            print("Adding nome_visualizzato_criptato column to Appartenenza_Famiglia...")
            try:
                cur.execute("ALTER TABLE Appartenenza_Famiglia ADD COLUMN nome_visualizzato_criptato TEXT;")
                con.commit()
                print("Column added successfully.")
            except Exception as e:
                print(f"Error adding column (maybe exists?): {e}")
                con.rollback()

    except Exception as e:
        print(f"Migration failed: {e}")

if __name__ == "__main__":
    migrate_db()
