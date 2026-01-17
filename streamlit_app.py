### A  Streamlit app for volleyball stat collection and tracking.
### Developed by Robert Patchin with assistance from ChatGPT and Bing Co-Pilot.
# -----------------------------------------------------------------------------
# import libraries 
# -----------------------------------------------------------------------------
import pandas as pd
import streamlit as st
import sqlite3

from datetime import datetime
from zoneinfo import ZoneInfo

from typing import Tuple, List, Optional

### not currently used
from dataclasses import asdict, dataclass
from typing import TypedDict, cast

# -----------------------------------------------------------------------------
# Database
# -----------------------------------------------------------------------------
DB_FILE = "vb_main.db"

# -----------------------------------------------------------------------------
# class declarations
# -----------------------------------------------------------------------------
### TODO evaluate - are dataclasses useful - should we update and use or delete?
@dataclass
class Team(TypedDict):
    team_id: int
    team_name: str
    team_abbv: str
    season: int
    club: Optional[str] = None
    hometown: Optional[str] = None
    coach: Optional[str] = None

class Player(TypedDict):
    player_id: int
    player_name: str
    player_jersey: int
    player_team: int
    player_position: Optional[int] = None

class TouchLog:
    """
    Data class representing a single touch in a possession
    """
    match_id: int
    set_id: int
    rally_id: int
    possession_id: int
    touch_seq: int
    player_id: int
    touch_type: int
    touch_result: int
    touch_quality: int

# -----------------------------------------------------------------------------
# Global Constants and Session State Initialization
# -----------------------------------------------------------------------------
# --- helper functions to load tables from database ---
def load_teams_from_database(season:int, db_path: str = DB_FILE) -> pd.DataFrame:
    """loads and returns a DataFrame from the Teams database table"""
    try:
        with sqlite3.connect(db_path) as conn:
            q = "SELECT * FROM Teams WHERE season = ?"
            df_teams = pd.read_sql_query(q, conn, params=(season,))
    except sqlite3.Error as e:
        print(f"SQLite error: {e} when loading teams")   
        df_teams = pd.DataFrame(columns=[
            "team_id", "team_name", "team_abbv", "club", "season", "hometown", "coach"])
    df_teams.set_index("team_id", inplace=True)
    return df_teams

def load_roster_from_database(team_ids:list, db_path: str = DB_FILE) -> pd.DataFrame:
    """loads and returns a DataFrame from the Roster database table"""
    t_placeholders = ",".join(["?"] * len(team_ids))
    try:
        with sqlite3.connect(db_path) as conn:
            df_poss = pd.read_sql_query("SELECT * FROM Positions", conn)
            long_position = {row["position_id"]: row["position_name"] for
                             _, row in df_poss.iterrows()}
            short_position = {row["position_id"]: row["position_abbv"] for
                              _, row in df_poss.iterrows()}
            q = f"SELECT * FROM Roster WHERE player_team IN ({t_placeholders})"
            df_roster = pd.read_sql_query(q, conn, params=team_ids)
        df_roster["player_position"] = df_roster["position_id"].replace(long_position)
        df_roster["player_abbv_position"] = df_roster["position_id"].replace(short_position)
    except sqlite3.Error as e:
        print(f"SQLite error: {e} when loading roster")
        df_roster = pd.DataFrame(columns=[
            "player_id", "player_name", "player_jersey", "position_id",
            "player_team", "player_position", "player_abbv_position"])
    df_roster.set_index("player_id", inplace=True)   
    return df_roster

def load_schedule_from_database(team_ids:list, db_path: str = DB_FILE) -> pd.DataFrame:
    """loads and returns a DataFrame from the Schedule database table"""
    t_placeholders = ",".join(["?"] * len(team_ids))
    try:
        with sqlite3.connect(db_path) as conn:
            q = f"SELECT * FROM Schedule WHERE us_team_id IN ({t_placeholders}) AND match_complete = 0"
            df_schedule = pd.read_sql_query(q, conn, params=team_ids)
            if not df_schedule.empty and "match_date" in df_schedule.columns:
                df_schedule["match_date"] = pd.to_datetime(
                    df_schedule["match_date"], errors="coerce")
    except sqlite3.Error as e:
        print(f"SQLite error: {e} when loading schedule")
        df_schedule = pd.DataFrame(columns=[
            "match_id", "match_date", "us_team_id", "them_team_id",
            "match_type", "match_location", "set_rules", "win_criteria",
            "winning_score", "last_set_score", "match_complete"])
    df_schedule.set_index("match_id", inplace=True)
    return df_schedule.sort_values("match_date")

# --- helper functions to load from database and cache ---
@st.cache_data
def load_dictionaries_from_database(db_path:str = DB_FILE) -> Tuple[
    dict, dict, dict, dict, dict, dict, dict, dict]:
    """
    Loads, returns, and caches 7 dictionaries from the database
    5 dictionaries are used to describe matches
    3 dictionaries are used to describe touches
    """
    try:
        with sqlite3.connect(db_path) as conn:
            df = pd.read_sql_query("SELECT * FROM Match_Types", conn)
            match_types = {row["type_id"]: row["match_type"] for
                           _, row in df.iterrows()}

            df = pd.read_sql_query("SELECT * FROM Match_Rules", conn)
            match_surface = {row["rule_id"]: row["rule_surface"] for
                             _, row in df.iterrows()}
            match_rules = {row["rule_id"]: row["rule_description"] for
                           _, row in df.iterrows()}
            match_num_players = {row["rule_id"]: row["rule_size"] for
                           _, row in df.iterrows()}

            df = pd.read_sql_query("SELECT * FROM Match_Criteria", conn)
            match_criteria = {row["criteria_id"]: row["criteria_description"] for
                              _, row in df.iterrows()}

            df = pd.read_sql_query("SELECT * FROM Touch_Types", conn)
            touch_types = {row["touch_type"]: row["type_id"] for
                           _, row in df.iterrows()}

            df = pd.read_sql_query("SELECT * FROM Touch_Results", conn)
            touch_results = {row["touch_result"]:row["result_id"] for
                             _, row in df.iterrows()}
            touch_results["IN PLAY"] = 2

            df = pd.read_sql_query("SELECT * FROM Touch_Qualities", conn)
            touch_quality = {row["quality_description"]:row["quality_id"] for
                             _, row in df.iterrows()}

        return match_types, match_surface, match_rules, match_num_players, match_criteria, touch_types, touch_results, touch_quality

    except sqlite3.Error as e:
        print(f"SQLite error: {e} when loading dictionaries")
        return {}, {}, {}, {}, {}, {}, {}

@st.cache_data
def load_data_from_database(season: int, db_path: str = DB_FILE) -> Tuple[
    pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Load, returns, and CACHES three dataframes from the database.
    - Filters Teams table by season.
    - Loads Rosters only for loaded teams.
    - Loads incomplete matches for teams in the selected season.
    """
    df_teams = load_teams_from_database(season, db_path)
    team_ids = df_teams.index.tolist()
    df_roster = load_roster_from_database(team_ids, db_path)
    df_schedule = load_schedule_from_database(team_ids, db_path)
    return df_teams, df_roster, df_schedule

# --- helper function to establish session state variables ---
def initialize_match() -> None:
    """
    Reset session state variables.
    """
    # match Dataframes 
    # tabular logs of current match state
    st.session_state.set_score_log_df = pd.DataFrame(columns=[
        "match_id", "set_id", "points_us", "points_them"])
    st.session_state.rally_log_df = pd.DataFrame(columns=[
        "match_id", "set_id", "rally_id", "points_us", "points_them",
        "rotation", "sanctions", "remarks", "serve_timestamp"])
    st.session_state.rotation_log_df = pd.DataFrame(columns=[
        "match_id", "set_id", "rally_id", 
        "rotation_slot", "player_id"])
    st.session_state.touch_log_df = pd.DataFrame(columns=[
        "match_id", "set_id", "rally_id", 
        "possession_seq", "touch_seq", "player_id",
        "touch_type", "touch_result", "touch_quality"])
    # session state table keys 
    # keep track of where we are
    st.session_state.set_id = 1
    st.session_state.rally_id = 0
    st.session_state.possession_id = 0
    st.session_state.touch_seq = 0
    st.session_state.rotation = 1
    # match flags and status
    st.session_state.dead_ball = True
    st.session_state.defend = False
    st.session_state.game_over = False
    st.session_state.sets_us = 0
    st.session_state.sets_them = 0
    st.session_state.score_us = 0
    st.session_state.score_them = 0
    st.session_state.lineup = {}
    st.session_state.remarks = ""
    st.session_state.sanctions = ""

def initialize_session_state() -> None:
    """
    Initialize session state variables.
    """
    if "match_id" not in st.session_state:
        st.session_state.match_id = None
        initialize_match()
    if "us_team_id" not in st.session_state:
        st.session_state.us_team_id = None
    if "them_team_id" not in st.session_state:
        st.session_state.them_team_id = None

initialize_session_state()
#TODO - determine dictionary usage and don't load if not used
MATCH_TYPE, SURFACE, RULES, NUM_PLAYERS, CRITERIA, TOUCH_TYPE, RESULT, QUALITY = load_dictionaries_from_database(DB_FILE)  

# -----------------------------------------------------------------------------
# U/I configuration and setup
# -----------------------------------------------------------------------------
st.set_page_config(page_title="VStat",
                   layout="wide",
                   page_icon=":volleyball:")
st.title("🏐 VolleyStat")

tabs = st.tabs([
    "Schedule",
    "Live Game Track"
])

# -----------------------------------------------------------------------------
# Scheduling
# -----------------------------------------------------------------------------
# --- Helper Utilities ---
def show_matches(df_schedule: pd.DataFrame, df_teams: pd.DataFrame)->dict:
    if df_schedule.empty or df_teams.empty:
        return None
    us_team = st.session_state.us_team_id
    team_abbr = df_teams.at[us_team, "team_abbv"]
    st.write(f"Schedule for {team_abbr}")
    df = df_schedule[df_schedule['us_team_id'] == us_team]
    df["match_type"] = df["match_type"].replace(MATCH_TYPE)
    df["set_rules"] = df["set_rules"].replace(RULES)
    df["win_criteria"] = df["win_criteria"].replace(CRITERIA)
    df["match_date"] = pd.to_datetime(df["match_date"]).dt.strftime("%Y-%m-%d")
    df = df.merge(df_teams, left_on="them_team_id",
                  right_on="team_id", 
                  right_index=True,
                  suffixes=("", "_opponent"))
    columns = ["match_date", "team_abbv",
               "match_location", "match_type",
                "set_rules", "win_criteria",
                "winning_score", "last_set_score"]
    df = df[columns]
    st.dataframe(
        df,
        hide_index=True, 
        column_config={
            "match_date": "Date",
            "team_abbv": "Against",
            "match_location": "At",
            "match_type": "Type",
            "set_rules": "Match",
            "win_criteria": "Win",
            "winning_score": "Play to",
            "last_set_score": "Last Set"
        }
    )
    game_dict = {}
    for k in df.index.to_list():
        game_dict[f"{df.loc[k, 'match_date']} vs {df.loc[k, 'team_abbv']}"] = k
    return game_dict

def add_new_team(df_teams: pd.DataFrame, season_YY: int) -> pd.DataFrame:
    col_1, col_2, col_3 = st.columns(3)
    with col_1:
        st.text_input("Club", key="new_team_club")
    with col_2:
        st.text_input("Team", key="new_team_name")
    with col_3:
        st.text_input("Abbreviation", key="new_team_abbv")

    if st.button("➕ Add Team"):
        try:
            with sqlite3.connect(DB_FILE) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO Teams (team_name, team_abbv, season, club)
                    VALUES (?, ?, ?, ?)
                """, (st.session_state.new_team_name, 
                      st.session_state.new_team_abbv, 
                      int(season_YY), 
                      st.session_state.new_team_club))
                conn.commit()
        except Exception as e:
            st.error(f"Failed to add team: {e}")
        st.cache_data.clear()
        df_teams = load_teams_from_database(season_YY)
        st.success(f"Team {st.session_state.new_team_abbv} added to {season_YY+2000}.")
    return df_teams

def add_new_match(df_teams: pd.DataFrame, df_schedule: pd.DataFrame, them_team_id: int) -> pd.DataFrame:
    us_abbv = df_teams.loc[st.session_state.us_team_id, "team_abbv"]
    them_abbv = df_teams.loc[them_team_id, "team_abbv"]
    st.write(f"Add New Match between {us_abbv} and {them_abbv}")
    # Inputs stored in session_state
    st.date_input("Match Date", key="new_match_date")
    st.text_input("Location", key="new_match_location")
    st.selectbox("Match Type", list(MATCH_TYPE.values()), key="new_match_type")
    st.selectbox("Set Rules", list(RULES.values()), key="new_set_rules")
    st.selectbox("Win Criteria", list(CRITERIA.values()), key="new_win_criteria")
    st.number_input("Play Set to", value=25, key="new_winning_score")
    st.number_input("Final Set Score", value=15, key="new_last_set_score")
    if st.button("➕ Add Match"):
        try:
            new_match_type = [k for k, v in MATCH_TYPE.items() if st.session_state.new_match_type in v][0]
            new_set_rules = [k for k, v in RULES.items() if st.session_state.new_set_rules in v][0]
            new_win_criteria = [k for k, v in CRITERIA.items() if st.session_state.new_win_criteria in v][0]
            with sqlite3.connect(DB_FILE) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO Schedule (match_date, us_team_id, them_team_id, match_type, match_location, set_rules, win_criteria, winning_score, last_set_score)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (st.session_state.new_match_date,
                      int(st.session_state.us_team_id),
                      int(them_team_id),
                      int(new_match_type), 
                      st.session_state.new_match_location,
                      int(new_set_rules),
                      int(new_win_criteria),
                      int(st.session_state.new_winning_score),
                      int(st.session_state.new_last_set_score)
                ))
                conn.commit()
        except Exception as e:
            st.error(f"Failed to add match: {e}")

        st.success("Match added to schedule.")
        st.cache_data.clear()
        df_schedule = load_schedule_from_database(df_teams['team_id'].tolist())
    return df_schedule

def assign_default_lineup(roster: pd.DataFrame, match: pd.DataFrame) -> None:
    roster = roster[roster["player_team"]==st.session_state.us_team_id]
    role_map = {1: "S", 2: "OH", 3: "M", 4: "RS", 5: "OH", 6: "M"}
    st.session_state.roster = dict(zip(roster["player_jersey"], roster["player_name"]))
    st.session_state.player_ids = dict(zip(roster["player_jersey"], roster.index))
    team_size = int(NUM_PLAYERS[match["set_rules"]])
    assigned = []
    for i in range(1, team_size+1):
        pos = role_map[i]
        df_t = roster[~roster["player_jersey"].isin(assigned)]
        df_p = df_t[df_t["player_abbv_position"] == pos]
        if len(df_p) > 0:
            assigned.append(df_p["player_jersey"].iloc[0])
        elif len(df_t) > 0:
            assigned.append(df_t["player_jersey"].iloc[-1])
        else:
            st.error("Not Enough Players")
            break
        st.session_state.lineup[i] = int(assigned[-1])

# --- Debugging Page ---------------------------------------------------------
#with tabs[2]:
#    st.dataframe(st.session_state.rally_log_df.tail(5))
#    st.write(st.session_state)

# --- Scheduling Page ---------------------------------------------------------
with tabs[0]:
    subtabs = st.tabs([
        "Select Match",
        "Add Opponent",
        "Add Match"
    ])

    ### Warning that a Match has already been selected
    if st.session_state.match_id is not None:
        st.warning(f"Match {st.session_state.match_id} is already in progress. Starting a new one will overwrite it.")
        st.markdown("---")

    ### Select season and team
    colA1, colA2 = st.columns(2)
    with colA1:
        season_YY = st.number_input("Select Season",
                        min_value=2025, max_value=2030,
                        key="select_season_key", disabled=True) - 2000
        df_teams, df_roster, df_schedule = load_data_from_database(season_YY, DB_FILE)
    with colA2:
        available_team_ids = df_roster["player_team"].unique() # only teams with rosters are available for our team
        available_teams = df_teams[df_teams.index.isin(available_team_ids)]
        selected_abbr = st.selectbox("Select Your Team", available_teams["team_abbv"])
        if len(available_teams) > 0:
            st.session_state.us_team_id = int(available_teams.loc[
                available_teams["team_abbv"] == selected_abbr].index[0])

    ### Add Opponent
    with subtabs[1]:
        df_teams = add_new_team(df_teams, season_YY)
        st.dataframe(df_teams, column_order=['club', 'team_name', 'team_abbv'], hide_index=True)

    ### Add Match against Opponent
    with subtabs[2]:
        idx = [i for i in df_teams.index.to_list() if i != st.session_state.us_team_id]
        opponent_teams = df_teams.loc[idx]
        if len(opponent_teams) > 0:
            opponent_abbr = st.selectbox("Select Opponent Team", opponent_teams["team_abbv"])
            them_team_id = int(opponent_teams.loc[
                opponent_teams["team_abbv"] == opponent_abbr].index[0])
            df_schedule = add_new_match(df_teams, df_schedule, them_team_id)
        else: st.info("No available teams to play")

    ###
    st.markdown("---")
    st.markdown("#### Upcoming Matches")    
    available_match_ids = show_matches(df_schedule, df_teams)
    if available_match_ids is None:
        st.info("No scheduled matches")
    else:
        selected_match_id = st.selectbox("Select Match", available_match_ids.keys(), index=None)
        if selected_match_id is not None:
            if st.button("🏐 Start Match!"):
                initialize_match()
                st.session_state.match_id = available_match_ids[selected_match_id]
                st.session_state.match = df_schedule.loc[st.session_state.match_id].to_dict()
                st.session_state.them_team_id = int(st.session_state.match["them_team_id"])
                assign_default_lineup(df_roster, st.session_state.match)
                opponent_abbr = df_teams.loc[st.session_state.them_team_id, "team_abbv"]
                st.success(f"Selected match against {opponent_abbr} on {st.session_state.match['match_date']}")

# -----------------------------------------------------------------------------
# Game Tracking
# -----------------------------------------------------------------------------
# --- Helper Utilities ---

def get_player_rotation() -> Tuple[list, list]:
    """
    returns two lists of integers
    list is rotation positions based on current rotation value
    """
    r = st.session_state.rotation
    team_size = int(NUM_PLAYERS[st.session_state.match["set_rules"]])

    if team_size == 6:
        front_row = [(i % 6 + 1) for i in range(2 + r, r - 1, -1)]
        back_row = [(i % 6 + 1) for i in range(r + 3, r + 5)] + [(r - 1) % 6 + 1]
    elif team_size == 4:
        front_row = [(i % 4 + 1) for i in range(1 + r, r - 1, -1)]
        back_row = [(i % 4 + 1) for i in range(r + 2, r + 3)] + [(r - 1) % 4 + 1]
    elif team_size == 2:
        back_row = [2, 1] if r == 1 else [1, 2]
        front_row = []
    elif team_size == 3:
        front_row = [(i % 3 + 1) for i in range(1 + r, r - 1, -1)]
        back_row = [(r+2) % 3 + 1] 
    else:                                                                                                                                                                                            
        st.error(f"Unrecognized Team Size: {team_size} {RULES[team_size]}")
        return [], []
    return front_row , back_row

def validate_lineup(roster: pd.DataFrame) -> bool:
    """Validate current lineup. If team omitted, infer from current_match."""
    team_size = int(NUM_PLAYERS[st.session_state.match["set_rules"]])
    jerseys = list(st.session_state.lineup.values())
    ### no nulls or duplicates
    if None in jerseys or len(jerseys) != team_size or len(set(jerseys)) != team_size:
        return False
    ### confirm all jerseys on us_team_id
    roster = roster[roster['player_team']==st.session_state.us_team_id]
    team_jerseys = roster['player_jersey'].to_list()
    return all(j in team_jerseys for j in jerseys)

def get_play_to_points() -> int:
    """uses set format and current set to deterimine point to win
    returns: int, min points to win"""
    criteria = CRITERIA[st.session_state.match['win_criteria']].lower()
    if any(item in criteria for item in ["5", "five"]):
        if st.session_state.set_id == 5:
            return st.session_state.match['last_set_score']
        else:
            return st.session_state.match['winning_score']
    else:
        if st.session_state.set_id == 3:
            return st.session_state.match['last_set_score']
        else:
            return st.session_state.match['winning_score']

def check_for_win() -> bool:
    """ evalutes set state and logic
    returns True if match is complete, otherwise False
    """
    criteria = CRITERIA[st.session_state.match['win_criteria']].lower()
    if "best" in criteria:
        if any(item in criteria for item in ["5", "five"]) and max(st.session_state.sets_us, 
                                                                   st.session_state.sets_them) == 3:
                return True
        elif any(item in criteria for item in ["3", "three"]) and max(st.session_state.sets_us,
                                                                      st.session_state.sets_them) == 2:
                return True
        else: return False
    elif any(item in criteria for item in ["3", "three"]) and sum(st.session_state.score_us, 
                                                                  st.session_state.score_them) == 3:
            return True
    else: 
        if sum(st.session_state.score_us, st.session_state.score_them) > 0:
            return True
        else: 
            return False

def rally_log_start() -> None:
    #log serve in start_rally_log
    serve_time = datetime.now(ZoneInfo("America/Los_Angeles")).strftime("%H:%M:%S")
    row = len(st.session_state.rally_log_df)
    serve = {
        "match_id": st.session_state.match_id,
        "set_id" : st.session_state.set_id,
        "rally_id" : st.session_state.rally_id,
        "points_us" : st.session_state.score_us,
        "points_them" : st.session_state.score_them,
        "rotation" : st.session_state.rotation,
        "sanctions" : st.session_state.sanctions,
        "remarks" : st.session_state.remarks,
        "serve_timestamp" : serve_time
    }
    st.session_state.rally_log_df.loc[row] = serve
    #log player rotations
    rot = {
        "match_id": st.session_state.match_id,
        "set_id" : st.session_state.set_id,
        "rally_id" : st.session_state.rally_id,
    }
    #loop through each player in lineup and add
    for k in st.session_state.lineup.keys():
        row = len(st.session_state.rotation_log_df)
        jersey = st.session_state.lineup[k]
        slot = {
            "rotation_slot": k,
            "player_id":st.session_state.player_ids[jersey]
        }
        slot |= rot
        st.session_state.rotation_log_df.loc[row] = slot
    #reset session_state variables
    st.session_state.defend = False
    st.session_state.dead_ball = False
    st.session_state.remarks = ""
    st.session_state.sanctions = ""
    return    

def set_log_over() -> None:
    row = len(st.session_state.set_score_log_df)
    score = {
        "match_id": st.session_state.match_id,
        "set_id" : st.session_state.set_id,
        "points_us" : st.session_state.score_us,
        "points_them" : st.session_state.score_them,
    }
    st.session_state.rally_log_df.loc[row] = score

def over_net() -> None:
    """increments the rally_step tracker"""
    st.session_state.possession_id += 2
    st.session_state.defend = False

def point_us(pt:int=1) -> None:
    """adds a point to score_us and checks for side-out and set/match win"""
    st.session_state.score_us += pt
    if st.session_state.possession_id % 2 == 1:
        st.session_state.rotation = (st.session_state.rotation + 1) % NUM_PLAYERS[st.session_state.match["set_rules"]]
    st.session_state.rally_id += 1
    st.session_state.possession_id = 0
    st.session_state.dead_ball = True
    st.session_state.defend = False

    if (
        st.session_state.score_us >= get_play_to_points()
        and st.session_state.score_us
        >= st.session_state.score_them + 2
    ):
        st.session_state.sets_us += 1
        set_log_over()
        st.session_state.game_over = check_for_win()
        if st.session_state.game_over == False:
            st.session_state.score_us = 0
            st.session_state.score_them = 0
            st.session_state.current_set += 1

def point_them(pt:int=1) -> None:
    """adds a point to score_them and checks for set/match win"""
    st.session_state.score_them += pt
    st.session_state.possession_id = 1
    st.session_state.rally_id += 1
    st.session_state.dead_ball = True
    st.session_state.defend = False


    if (
        st.session_state.score_them >= get_play_to_points()
        and st.session_state.score_them
        >= st.session_state.score_us + 2
    ):
        st.session_state.sets_them += 1
        set_log_over()
        st.session_state.game_over = check_for_win()
        if st.session_state.game_over == False:
            st.session_state.score_us = 0
            st.session_state.score_them = 0
            st.session_state.current_set += 1

def display_scoreboard(match_teams: List[str]) -> None:
    # show header with teams and scores
    header_col = st.columns([1, 3, 1])
    with header_col[0]:
        st.metric(f"Sets Us: {st.session_state.sets_us}",
            st.session_state.score_us)
    with header_col[1]:
        st.subheader(f"{match_teams[0]}   vs   {match_teams[1]}")
    with header_col[2]:
        st.metric(f"Sets Them: {st.session_state.sets_them}",
            st.session_state.score_them)        
    st.markdown("---")
    return

def display_start_set(match_teams: List[str]) -> None:
    # at start of set - assign players, rotation, and first serve
    start_col = st.columns([1, 2])
    st.session_state.rotation = start_col[0].slider("Start in Rotation:",
        min_value=1,
        max_value=NUM_PLAYERS[st.session_state.match["set_rules"]],
        width=200,
        value=1)
    
    first_serve = start_col[1].radio("First to serve:", 
        match_teams,
        index=0, 
        horizontal=True)
    st.session_state.rally_id = 0
    st.session_state.possession_id = 0 if first_serve == match_teams[0] else 1
    
    # draw net
    st.markdown("---")
    # layout players below net based on set_rules
    if int(NUM_PLAYERS[st.session_state.match["set_rules"]]) == 6:
        players_col = st.columns(3)
    else: 
        players_col = st.columns(2)
            
    front_row, back_row = get_player_rotation()
    options = list(st.session_state.roster.keys())

    for i, key in enumerate(front_row):
        idx = options.index(st.session_state.lineup[key])
        #To do - add function that displays #Jersey Name
        new_player = players_col[i].selectbox(f"Front rotation {key}",
            options,
            format_func = lambda o: f"# {o} {st.session_state.roster[o]}",
            index=idx
            )
        if new_player:
            st.session_state.lineup[key] = int(new_player)

    for i, key in enumerate(back_row):
        idx = options.index(st.session_state.lineup[key])
        if len(back_row) == 1: i = 1
        new_player = players_col[i].selectbox(f"Back rotation {key}",
            options,
            format_func = lambda o: f"# {o} {st.session_state.roster[o]}",
            index=idx
            )
        if new_player:
            st.session_state.lineup[key] = int(new_player)

    if not validate_lineup(df_roster):
        st.error("Invalid Lineup")
        #TODO inhibit continuing until valid_lineup
    return

def display_lineup() -> None:
    st.write(f"Current Rotation: {st.session_state.rotation}" +
        f"   --   Rally: {st.session_state.rally_id}")
    if int(NUM_PLAYERS[st.session_state.match["set_rules"]]) == 6:
        players_col = st.columns(3)
    else: 
        players_col = st.columns(2)
    
    front_row, back_row = get_player_rotation()
    for i, key in enumerate(front_row):
        with players_col[i]:
            st.write(f"#{st.session_state.lineup[key]} {st.session_state.roster[st.session_state.lineup[key]]}")
    for i, key in enumerate(back_row):
        if len(back_row) == 1: i = 1
        with players_col[i]:
            st.write(f"#{st.session_state.lineup[key]} {st.session_state.roster[st.session_state.lineup[key]]}")

def display_serve() -> None:
    def _touch_log_serve(jersey: int, result:str, quality: str) -> None:
        row = len(st.session_state.touch_log_df)
        touch = {
            'match_id': st.session_state.match_id,
            'set_id': st.session_state.set_id,
            'rally_id': st.session_state.rally_id,
            'possession_seq': st.session_state.possession_id,
            'touch_seq': 0,
            'player_id': st.session_state.player_ids[jersey],
            'touch_type': 1,
            'touch_result': RESULT[result],
            'touch_quality': QUALITY[quality],
        }
        st.session_state.touch_log_df.loc[row] = touch

    _, back_row = get_player_rotation()
    server = st.session_state.lineup[back_row[-1]]
    st.markdown(f"#### #{server} {st.session_state.roster[server]} to serve:")
    serve_col = st.columns(2)
    result_serve = serve_col[0].radio("Serve result:", 
        ["Ace", "In Play", "Error"],
        horizontal=True)
    result_serve = result_serve.upper()
    grades = ['Strong', 'Weak']
    if result_serve == "ERROR": grades.append('Fault')
    q = serve_col[0].radio("Grade:", 
                grades,
                horizontal=True)
    if serve_col[1].button("Record Serve"):
        rally_log_start()
        _touch_log_serve(server, result_serve.upper(), q.upper())
        if (result_serve.upper() == "ACE"):
            point_us()
        elif "ERROR" in result_serve.upper():
            point_them()
        else:
            over_net()
        st.rerun()

def display_opp(opp_play:str) -> bool:
    st.markdown(f"#### {match_teams[1]} to {opp_play}:")

    opponent_col = st.columns(2)
    if opp_play.upper() == "SERVE":
        options = ["Serve", "Serve - Error"]
    else:
        options = ["Attack/In Play", "Attack/Defend - Error"]
    
    opponent_result = opponent_col[0].radio(f"{opp_play} result:",
        options,
        horizontal=True)
    
    if opponent_col[1].button(f"Record {match_teams[1]}"):
        if "SERVE" in opponent_result.upper():
            rally_log_start()
        if "ERROR" in opponent_result.upper():
            point_us()
            st.session_state.defend = False
            st.rerun()
        else: st.session_state.defend = True

def display_defend(t:str) -> None:
    def _get_results(touch:str) -> List[str]:
        if touch == "PASS":
            return ["", "Pass", "In Play", "Error"]
        if touch == "SET":
            return ["", "Set", "Assist", "In Play", "Error"]
        if touch == "ATTACK":
            return ["", "Kill", "In Play", "Error"]
        if touch == "DIG":
            return ["", "Dig", "Miss"]
        if touch == "BLOCK":
            return ["", "Stuff", "Assist", "In Play", "Error", "Tip"]

    def _get_qualities(touch:str) -> List[str]:
        if touch == "PASS":
            return ["", "Fair", "Good", "Perfect", "Error"]
        if touch in ["SET", "ATTACK", "DIG", "ASSIST"]:
            return ["", "Weak", "Strong"]
        if touch == "BLOCK":
            return ["", "Weak" , "Strong", "Tool", "Fault"]

    def _touch_log_(jersey: int, seq:int, touch_type:str, result:str, quality: str) -> None:
        row = len(st.session_state.touch_log_df)
        result = 'ZERO' if result == 'IN PLAY' else result
        result = 'TOUCH' if result == 'TIP' else result
        result = 'TOUCH' if result in list(TOUCH_TYPE.keys()) else result
        touch = {
            'match_id': st.session_state.match_id,
            'set_id': st.session_state.set_id,
            'rally_id': st.session_state.rally_id,
            'possession_seq': st.session_state.possession_id,
            'touch_seq': seq,
            'player_id': st.session_state.player_ids[jersey],
            'touch_type': TOUCH_TYPE[touch_type],
            'touch_result': RESULT[result],
            'touch_quality': QUALITY[quality],
        }
        st.session_state.touch_log_df.loc[row] = touch

    st.markdown(f"#### {t}:")
    st.markdown("---")
    st.session_state.roster[None] = None
    options = list(st.session_state.lineup.values())
    touch_col = st.columns(4)
    if st.session_state.possession_id != 1:
        with touch_col[0]:
            BlockerA = st.selectbox(
                "Block - Player",
                options = options,
                format_func = lambda o: f"# {o} {st.session_state.roster[o]}",
                index=None,
            )
            BlockerB = st.selectbox(
                "Block - Assist",
                options = options,
                format_func = lambda o: f"# {o} {st.session_state.roster[o]}",
                index=None,
            )
            results = _get_results("BLOCK")
            resultB = st.selectbox(
                "Block - Result",
                options=results,
                index=0
            )
            quality = _get_qualities("BLOCK")
            qualityB = st.selectbox(
                "Block - Quality",
                options=quality
            )
    else: BlockerA, BlockerB, resultB = None, None, None
    touch_players = {}
    touch_touch = {}
    touch_results = {}
    touch_quality = {}

    with touch_col[1]:
        touch_players[1] = st.selectbox(
            "Touch 1 - Player",
            options = options,
            format_func = lambda o: f"# {o} {st.session_state.roster[o]}",
            index=None,
        )
        touch_touch[1] = st.selectbox("Touch 1 - Type",
            ["Dig", "Pass", "Set", "Attack"],
        )
        results = _get_results(touch_touch[1].upper())
        touch_results[1] = st.selectbox(
            "Touch 1 - Result",
            results,
        )
        quality = _get_qualities(touch_touch[1].upper())
        touch_quality[1] = st.selectbox(
            "Touch 1 - Quality",
            options=quality
        )
    with touch_col[2]:
        touch_players[2] = st.selectbox(
            "Touch 2 - Player",
            options = options,
            format_func = lambda o: f"# {o} {st.session_state.roster[o]}",
            index=None,
        )
        touch_touch[2] = st.selectbox(
            "Touch 2 - Type",
            ["Pass", "Set", "Attack"],
        )
        results = _get_results(touch_touch[2].upper())
        touch_results[2] = st.selectbox(
            "Touch 2 - Result",
            results,
        )
        quality = _get_qualities(touch_touch[2].upper())
        touch_quality[2] = st.selectbox(
            "Touch 2 - Quality",
            options=quality
        )
    with touch_col[3]:
        touch_players[3] = st.selectbox(
            "Touch 3 - Player",
            options = options,
            format_func = lambda o: f"# {o} {st.session_state.roster[o]}",
            index=None,
        )
        touch_touch[3] = st.selectbox(
            "Touch 3 - Type",
            ["Pass", "Attack"],
        )
        results = _get_results(touch_touch[3].upper())
        touch_results[3] = st.selectbox(
            "Touch 3 - Result",
            ["Kill", "Over", "Error"],
        )
        quality = _get_qualities(touch_touch[3].upper())
        touch_quality[3] = st.selectbox(
            "Touch 3 - Quality",
            options=quality)
        
    if st.button("Record Volley"):

        #touch_seq is {0: SERVE, 1: ONE, 2: TWO, 3: THREE, 4: BLOCK, 5: BLOCK}
        if BlockerB:
            _touch_log_(BlockerB, 5, "BLOCK", resultB.upper(), qualityB.upper())
        if BlockerA:
            _touch_log_(BlockerA, 4, "BLOCK", resultB.upper(), qualityB.upper())
            if resultB.upper() == "STUFF" or resultB.upper() =="ASSIST":
                point_us()
                st.rerun()
            elif resultB.upper() == "ERROR":
                point_them()
                st.rerun()
            elif resultB.upper() == "IN PLAY" or resultB.upper() == "ZERO":
                over_net()
                st.rerun()
        #for k in list(touch_players.keys()):
        for k in range(1,4):
            _touch_log_(touch_players[k], k, touch_touch[k].upper(), touch_results[k].upper(), touch_quality[k].upper())
            if touch_results[k].upper() == 'KILL':
                point_us()
                break
            elif touch_results[k].upper() == 'ERROR':
                point_them()
                break
            elif touch_results[k].upper() =="IN PLAY" or touch_results[k] =="ZERO":
                over_net()
                break
        st.rerun()
        return

def display_dead_ball() -> None:
    st.markdown("---")
    st.markdown("Deadball Actions:")
    dead_ball_column_A = st.columns([1, 2])
    with dead_ball_column_A[0]:
        #TODO update to show names vs jersey numbers
        #TODO ensure button press updates player display
        sub_out = st.selectbox("Sub Out",
            options=list(st.session_state.lineup.values()),
            format_func = lambda o: f"# {o} {st.session_state.roster[o]}",
            index=None)
        sub_in = st.selectbox("Sub In", 
            options=[j for j in st.session_state.roster.keys() if j not in st.session_state.lineup.values()],
            format_func = lambda o: f"# {o} {st.session_state.roster[o]}",
            index=None)
        if st.button("Record Sub"):
            for key, val in st.session_state.lineup.items():
                if val == sub_out:
                    st.session_state.lineup[key] = sub_in
                    st.success(f"Subbed out {sub_out} for {sub_in}")
                    break
            st.rerun()
    with dead_ball_column_A[1]:
        st.session_state.sanctions = st.text_input("Sanctions:", "")
        st.session_state.remarks = st.text_input("Remarks:", "")

    st.markdown("---")
    dead_ball_column_B = st.columns([1, 1, 1])

    with dead_ball_column_B[0]:
        add_point = st.radio("Adjust Score:", 
            match_teams,
            index=None, horizontal=False)
        #TODO need buisness rules for ralley that ends in whistle/no point
        if st.button("Adjust + Score"):
            if add_point == match_teams[0]:
                point_us()
            elif add_point == match_teams[1]:
                point_them()
        if st.button("Adjust - Score"):
            if add_point == match_teams[0]:
                st.session_state.score_us += -1
            elif add_point == match_teams[1]:
                st.session_state.score_them += -1
    with dead_ball_column_B[1]:
        #TODO validate - rewrite undo helper function
        if st.button("Undo Last"):
            undo_last_line()

def display_live_ball() -> None:
    #TODO add functions to support whistle, ending rally w/o point
    return

def display_game_over() -> None:
    st.markdown("## Game Over")
    st.markdown(f"#{match_teams[0]}: {st.session_state.sets_us} ")
    st.markdown(f"#{match_teams[1]}: {st.session_state.sets_them} ")

    #TODO update to show # serves # aces and ace %
    st.markdown("#### Serves:")
    serves_df = st.session_state.touch_log_df[
        st.session_state.touch_log_df['possession_seq'] == 0].groupby(
            by = ['player_id']).count()
    st.dataframe(serves_df)

    #TODO update to show # passes # digs average passing score
    st.markdown("#### Serve Receive:")
    serve_receive_df = st.session_state.touch_log_df[
        st.session_state.touch_log_df['possession_seq'] == 1]
    serve_receive_df = serve_receive_df[
        serve_receive_df['touch_seq'] == 1].groupby(
            by = ['player_id']).count()
    st.dataframe(serve_receive_df)

# --- Game Tracking Page ---
with tabs[1]:
    if not st.session_state.match_id:
        st.subheader("Game Tracking")
        st.info("Start a match from Scheduling to begin tracking")

    else:
        match_teams = [df_teams.loc[st.session_state.us_team_id, "team_abbv"],
                       df_teams.loc[st.session_state.them_team_id, "team_abbv"]]
        display_scoreboard(match_teams)
        if st.session_state.score_us + st.session_state.score_them == 0 and not st.session_state.game_over:
            display_start_set(match_teams)
        else:
            display_lineup()
        st.markdown("---")

        # if game is over - take end of game actions
        if st.session_state.game_over == True:
            #TODO - mark game as complete
            #TODO - store df in database
            display_game_over()

        # if game is NOT over and it's our serve -
        elif st.session_state.possession_id == 0:
            display_serve()

        # if it's not our serve - we are defending, either a serve or an attack
        else:
            opp_play = "Serve" if st.session_state.possession_id == 1 else "Volley"
            if not st.session_state.defend:
                display_opp(opp_play)
            if st.session_state.defend:
                t = "Serve-Receive" if opp_play.upper()=="SERVE" else "Defend-to-Attack"
                display_defend(t)
       
        #TODO determine appropriate display for deadball actions
        if st.session_state.dead_ball == True and st.session_state.game_over == False:
            display_dead_ball()
        #TODO add whistle dead to jump ball option
        if st.session_state.dead_ball == False and st.session_state.game_over == False:
            display_live_ball()