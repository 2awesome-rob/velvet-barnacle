### stub for manually updating the database ####

import sqlite3
DB_PATH = "main.db"

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

#print_table_columns('Teams', DB_PATH)
#print_table_contents('Teams', DB_PATH)
print_table_contents('Teams', DB_PATH)



def add_game(db_path, match_date, us_team_id, them_team_id, match_type, match_location, set_rules, win_criteria):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT INTO Schedule (
            match_date, us_team_id, them_team_id, match_type, match_location, set_rules, win_criteria
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (match_date, us_team_id, them_team_id, match_type, match_location, set_rules, win_criteria))
    conn.commit()
    conn.close()

def add_player(db_path, player_name, player_jersey, position_id, player_team):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("""
        INSERT INTO Roster (
            player_name, player_jersey, position_id, player_team
        ) VALUES (?, ?, ?, ?)
    """, (player_name, player_jersey, position_id, player_team))
    conn.commit()
    conn.close()


def remove_entry(db_path, table, table_id, val):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute(f"DELETE FROM {table} WHERE {table_id} is {val};")
    conn.commit()
    conn.close()

#remove_entry(DB_PATH, "Teams", 'team_id', 6)
