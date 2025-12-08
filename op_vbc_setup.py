### stub for manually updating the database ####

import sqlite3
DB_PATH = "OP_VBC.db"

#initialize_database(DB_PATH)

def print_table_columns(table_name, db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(f"SELECT * FROM {table_name}")
    cols = [desc[0] for desc in cursor.description]
    print(f"{table_name} columns: {cols}")
    conn.close()


def print_table_contents(table_name, db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(f"SELECT * FROM {table_name}")
    rows = cursor.fetchall()
    for row in rows:
        print(row)
    conn.close()


print_table_columns('Player_Roster', DB_PATH)

print_table_contents('Player_Roster', DB_PATH)
