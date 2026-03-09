import psycopg2
from psycopg2 import sql

try:
    # Connect to the default postgres database
    conn = psycopg2.connect(
        dbname='postgres',
        user='postgres',
        password='mollen1234',
        host='localhost',
        port='5432'
    )
    conn.autocommit = True
    cursor = conn.cursor()
    
    # Create the database
    cursor.execute(sql.SQL("CREATE DATABASE {}").format(
        sql.Identifier('school_portal')
    ))
    print("Database 'school_portal' created successfully!")
    
    cursor.close()
    conn.close()
except psycopg2.errors.DuplicateDatabase:
    print("Database 'school_portal' already exists!")
except Exception as e:
    print(f"Error: {e}")
