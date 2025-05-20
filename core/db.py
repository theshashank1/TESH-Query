from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError


def connect_database(db_url: str) -> None:
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

    except SQLAlchemyError as e:
        print(f"[SQL ERROR] {e}")


def disconnect_database(engine) -> None:
    """
    Disconnect from the database.

    Args:
        engine: The database engine.
    """
    try:
        engine.dispose()
        print("✅ Database connection closed.")
    except SQLAlchemyError as e:
        print(f"[SQL ERROR] {e}")


if __name__ == "__main__":
    db_url = "sqlite:///sqlite.db"
    conn = connect_database(db_url)
    disconnect_database(conn)
