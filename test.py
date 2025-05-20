import os

from dotenv import load_dotenv
from sqlalchemy import text

from core import db

# Load environment variables
load_dotenv()


def main():
    db_url = os.getenv("DATABASE_URL")
    print(f"Using DB URL: {db_url}")

    if not db_url:
        print("❌ DATABASE_URL not found in environment variables.")
        return

    engine = None
    print("🔌 Connecting to the database...")
    try:
        engine = db.connect_database(db_url)
        print("✅ Engine created.")

        with engine.connect() as connection:
            print("✅ Connection established.")
            result = connection.execute(text("SELECT * FROM employees LIMIT 5;"))
            for row in result:
                print(row)
            print("✅ Query executed successfully.")
    except Exception as e:
        print(f"❌ An error occurred: {e}")
    finally:
        if engine:
            db.disconnect_database(engine)
            print("🔌 Database connection closed.")


if __name__ == "__main__":
    main()
