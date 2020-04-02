import configparser
import os
import psycopg2
from sql_queries import create_table_queries, drop_table_queries


def drop_tables(cur, conn):
    """ Drops all the analytics tables as well as the staging tables."""
    for query in drop_table_queries:
        cur.execute(query)
        conn.commit()


def create_tables(cur, conn):
    """ Creates both the staging and analytics tables."""
    for query in create_table_queries:
        cur.execute(query)
        conn.commit()


def main():
    config = configparser.ConfigParser()
    config.read('dwh.cfg')

    conn = psycopg2.connect(
        "host={} dbname={} user={} password={} port={}".format(
            config['REDSHIFT']['ENDPOINT'],
            config['REDSHIFT']['DB_NAME'],
            config['REDSHIFT']['DB_USER'],
            config['REDSHIFT']['DB_PASSWORD'],
            config['REDSHIFT']['DB_PORT']
        )
    )
    cur = conn.cursor()

    drop_tables(cur, conn)
    create_tables(cur, conn)

    conn.close()


if __name__ == "__main__":
    main()
