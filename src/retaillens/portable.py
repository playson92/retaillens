"""Authenticate the preserved Windows Portable cluster before trusting its endpoint."""

import ntpath

import psycopg


def local_parameters(parameters):
    if parameters["host"] not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("Portable requires an explicitly local database endpoint")
    return dict(parameters)


def assert_data_directory(connection, expected):
    observed = connection.execute("SHOW data_directory").fetchone()[0]
    if not ntpath.isabs(observed) or ntpath.normcase(ntpath.normpath(observed)) != ntpath.normcase(
        ntpath.normpath(str(expected))
    ):
        raise ValueError("Connected PostgreSQL is not the preserved RetailLens Portable cluster")
    return observed


def inspect_portable(parameters, expected):
    parameters = local_parameters(parameters)
    with psycopg.connect(
        **parameters,
        connect_timeout=5,
        application_name="retaillens-portable-identity",
        options="-c default_transaction_read_only=on",
    ) as connection:
        connection.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        directory = assert_data_directory(connection, expected)
        version = connection.execute("SELECT version()").fetchone()[0]
    return {
        "host": parameters["host"],
        "port": int(parameters["port"]),
        "database": parameters["dbname"],
        "data_directory": directory,
        "postgres_version": version,
        "read_only": True,
    }
