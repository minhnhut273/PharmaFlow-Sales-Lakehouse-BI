"""Read-only MongoDB connection check."""

from connection import MongoConnectionError, connect_mongodb
from product_knowledge import COLLECTION_NAME, DATABASE_NAME


def main() -> int:
    client = None
    try:
        client, database, collection_name = connect_mongodb(
            database_name=DATABASE_NAME,
            collection_name=COLLECTION_NAME,
        )
        print(
            "MongoDB ping successful; "
            f"database={database.name}, configured_collection={collection_name}."
        )
        return 0
    except MongoConnectionError as error:
        print(str(error))
        return 1
    finally:
        if client is not None:
            client.close()


if __name__ == "__main__":
    raise SystemExit(main())
