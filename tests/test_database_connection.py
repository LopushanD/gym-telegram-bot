import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.database import database_connection, initialize_database


class DatabaseConnectionTests(unittest.TestCase):
    def setUp(self):
        directory = self.enterContext(tempfile.TemporaryDirectory())
        self.database_path = Path(directory) / "test.sqlite3"

    def assert_connection_closed(self, connection):
        with self.assertRaises(sqlite3.ProgrammingError):
            connection.execute("SELECT 1")

    def test_success_commits_and_closes_connection(self):
        with database_connection(self.database_path) as connection:
            connection.execute("CREATE TABLE records (value INTEGER)")
            connection.execute("INSERT INTO records VALUES (42)")

        self.assert_connection_closed(connection)
        with database_connection(self.database_path) as reader:
            self.assertEqual([(42,)], reader.execute("SELECT value FROM records").fetchall())

    def test_exception_rolls_back_and_closes_connection(self):
        with database_connection(self.database_path) as connection:
            connection.execute("CREATE TABLE records (value INTEGER)")
            connection.execute("INSERT INTO records VALUES (1)")

        with self.assertRaisesRegex(ValueError, "operation failed"):
            with database_connection(self.database_path) as connection:
                connection.execute("INSERT INTO records VALUES (2)")
                raise ValueError("operation failed")

        self.assert_connection_closed(connection)
        with database_connection(self.database_path) as reader:
            self.assertEqual([(1,)], reader.execute("SELECT value FROM records").fetchall())

    def test_transaction_exit_failure_still_closes_connection(self):
        connection = MagicMock()
        connection.__exit__.side_effect = sqlite3.OperationalError("commit failed")
        with patch("src.database.sqlite3.connect", return_value=connection):
            with self.assertRaisesRegex(sqlite3.OperationalError, "commit failed"):
                with database_connection(self.database_path):
                    pass

        connection.close.assert_called_once_with()

    def test_initialization_closes_connection_and_releases_database_file(self):
        connect = sqlite3.connect
        connections = []

        def track_connection(database_path):
            connection = connect(database_path)
            connections.append(connection)
            self.addCleanup(connection.close)
            return connection

        with patch("src.database.sqlite3.connect", side_effect=track_connection):
            initialize_database(self.database_path)
            initialize_database(self.database_path)

        for connection in connections:
            self.assert_connection_closed(connection)
        self.database_path.unlink()


if __name__ == "__main__":
    unittest.main()
