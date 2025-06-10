from sqlalchemy import create_engine
from sqlalchemy.engine import Engine


def connect_database(db_url: str) -> Engine | None:
    """
    Connect to a database using the provided URL.

    Args:
        db_url (str): The database connection URL.
    """
    try:
        engine = create_engine(db_url, echo=True)
        engine.connect()
        print("✅ Database connection established.")
        return engine

    except Exception as e:  # Catching a broader Exception for now for robustness
        print(f"[SQL ERROR] {e}")


def disconnect_database(engine: Engine) -> None:
    """
    Disconnect from the database.

    Args:
        engine (Engine): The database engine.
    """
    try:
        engine.dispose()
        print("✅ Database connection closed.")
    except Exception as e:  # Catching a broader Exception for now for robustness
        print(f"[SQL ERROR] {e}")


if __name__ == "__main__":
    db_url = "sqlite:///sqlite.db"
    conn = connect_database(db_url)
    disconnect_database(conn)
