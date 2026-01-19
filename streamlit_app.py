### A Streamlit app for volleyball stat collection and tracking.
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
# class declarations
# -----------------------------------------------------------------------------
### TODO evaluate - are dataclasses useful - should we update and use or delete?
@dataclass
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
DB_FILE = "vb_main.db"
# --- helper functions to load tables from database ---
def load_teams_from_database(season:int, db_path:str=DB_FILE) -> pd.DataFrame:
    """loads and returns a DataFrame from the Teams database table"""
    try:
        with sqlite3.connect(db_path) as conn:
            q = "SELECT * FROM Teams WHERE season = ?"
            df_teams = pd.read_sql_query(q, conn, params=(season,))
    except sqlite3.Error as e:
        print(f"SQLite error: {e} when loading teams")
        df_teams = pd.DataFrame(columns=[
            "team_id", "team_name", "team_abbv", "club",
            "season", "hometown", "coach"])
    df_teams.set_index("team_id", inplace=True)
    return df_teams

def load_roster_from_database(team_ids:list, db_path:str=DB_FILE) -> pd.DataFrame:
    """loads and returns a DataFrame from the Roster database table"""
    t_placeholders = ",".join(["?"] * len(team_ids))
    try:
        with sqlite3.connect(db_path) as conn:
            df_poss = pd.read_sql_query("SELECT * FROM Positions", conn)
            long_position = {row["position_id"]: row["position_name"] for
                             _, row in df_poss.iterrows()}
            short_position = {row["position_id"]: row["position_abbv"] for
                              _, row in df_poss.iterrows()}
            q = f"SELECT * FROM Roster WHERE team_id IN ({t_placeholders})"
            df_roster = pd.read_sql_query(q, conn, params=team_ids)
        df_roster["player_position"] = df_roster["position_id"].replace(long_position)
        df_roster["player_abbv_position"] = df_roster["position_id"].replace(short_position)
    except sqlite3.Error as e:
        print(f"SQLite error: {e} when loading roster")
        df_roster = pd.DataFrame(columns=[
            "player_id", "player_name", "player_jersey", "position_id",
            "team_id", "player_position", "player_abbv_position"])
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
            "match_type", "match_location", "win_criteria",
            "winning_score", "last_set_score", "match_complete"])
    df_schedule.set_index("match_id", inplace=True)
    return df_schedule.sort_values("match_date")

# --- helper functions to load from database and cache ---
@st.cache_data
def load_dictionaries_from_database(db_path:str = DB_FILE) -> Tuple[
    dict, dict, dict, dict, dict, dict]:
    """
    Loads, returns, and caches 6 dictionaries from the database
    3 dictionaries are used to describe matches
    3 dictionaries are used to describe touches
    """
    try:
        with sqlite3.connect(db_path) as conn:
            df = pd.read_sql_query("SELECT * FROM Match_Types", conn)
            match_types = {row["type_id"]: row["match_type"] for
                           _, row in df.iterrows()}

            df = pd.read_sql_query("SELECT * FROM Match_Rules", conn)
            match_num_players = {row["rule_id"]: row["rule_size"] for
                           _, row in df.iterrows()}

            df = pd.read_sql_query("SELECT * FROM Match_Criteria", conn)
            match_criteria = {row["criteria_id"]: row["criteria_description"] for
                              _, row in df.iterrows()}

            df = pd.read_sql_query("SELECT * FROM Touch_Types", conn)
            touch_types = {row["type_id"]: row["touch_type"] for
                           _, row in df.iterrows()}

            df = pd.read_sql_query("SELECT * FROM Touch_Results", conn)
            touch_results = {row["result_id"]:row["touch_result"] for
                             _, row in df.iterrows()}

            df = pd.read_sql_query("SELECT * FROM Touch_Qualities", conn)
            touch_quality = {row["quality_id"]:row["quality_description"] for
                             _, row in df.iterrows()}

        return match_types, match_num_players, match_criteria, touch_types, touch_results, touch_quality

    except sqlite3.Error as e:
        print(f"SQLite error: {e} when loading dictionaries")
        return {}, {}, {}, {}, {}, {} 

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

# --- helper functions to establish session state variables ---
def initialize_session_state() -> None:
    """
    Initialize session state variables.
    """
    if "match_id" not in st.session_state:
        st.session_state.match_id = None
    if "us_team_id" not in st.session_state:
        st.session_state.us_team_id = None
    if "them_team_id" not in st.session_state:
        st.session_state.them_team_id = None

def initialize_match(m_id:int, df:pd.DataFrame) -> None:
    """
    Reset session state variables.
    """
    # match Dataframes - tabular logs of the match
    st.session_state.set_score_log_df = pd.DataFrame(columns=[
        "match_id", "set_id", "points_us", "points_them"])
    st.session_state.rally_log_df = pd.DataFrame(columns=[
        "match_id", "set_id", "rally_id", "points_us", "points_them",
        "rotation", "sanctions", "remarks", "serve_timestamp"])
    st.session_state.rotation_log_df = pd.DataFrame(columns=[
        "match_id", "set_id", "rally_id", "rotation",
        "rotation_slot", "player_id"])
    st.session_state.touch_log_df = pd.DataFrame(columns=[
        "match_id", "set_id", "rally_id", 
        "possession_seq", "touch_seq", "player_id",
        "touch_type", "touch_result", "touch_quality"])
    # Add match_id and data to session state
    st.session_state.match_id = m_id
    st.session_state.match = df.loc[st.session_state.match_id].to_dict()
    st.session_state.them_team_id = int(st.session_state.match["them_team_id"])
    # session state variables
    # keep track of where we are, table keys
    st.session_state.set_id = 1
    st.session_state.rally_id = 0
    st.session_state.possession_id = 0
    st.session_state.touch_seq = 0
    st.session_state.rotation = 1
    st.session_state.lineup = {}
    st.session_state.liberos = []
    # current score
    st.session_state.points_to_win = st.session_state.match['winning_score']
    st.session_state.sets_us = 0
    st.session_state.sets_them = 0
    st.session_state.score_us = 0
    st.session_state.score_them = 0
    # current flags, status, notes
    st.session_state.game_over = False
    st.session_state.active_set = False
    st.session_state.subs = 0
    st.session_state.to = 0
    initialize_rally()

def initialize_rally() -> None:
    st.session_state.defend = False
    st.session_state.whistle = False
    st.session_state.remarks = ""
    st.session_state.sanctions = ""

# --- helper function to establish session state variables ---
initialize_session_state()
MATCH_TYPE, NUM_PLAYERS, CRITERIA, TOUCH_TYPE, RESULT, QUALITY = load_dictionaries_from_database(DB_FILE)  

# -----------------------------------------------------------------------------
# Set up and U/I configuration
# -----------------------------------------------------------------------------

st.set_page_config(page_title="VStat",
                   layout="wide",
                   page_icon=":volleyball:")
st.title("🏐 VolleyStat")

tabs = st.tabs([
    "Schedule",
    "Live Game Track",
    "Debug"
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
    st.write(f"Match Schedule for {team_abbr}")
    df = df_schedule[df_schedule['us_team_id'] == us_team]
    df["match_type"] = df["match_type"].replace(MATCH_TYPE)
    df["set_rules"] = df["set_rules"].replace(NUM_PLAYERS)
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
            "set_rules": "Players",
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
    cols = st.columns(2)
    with cols[0]:
        new_match_date = st.date_input("Date")
        new_match_time = datetime.now(ZoneInfo("America/Los_Angeles")).strftime("%H:%M")
        new_match_location = st.text_input("Location")
        new_match_type_v = st.selectbox("Type",
            list(MATCH_TYPE.values()),
            format_func = lambda o: o.title(),
            )
        new_set_rules_v = st.selectbox("# Players", 
            list(NUM_PLAYERS.values()),
            format_func = lambda o:f"{o} Players",
            )
    with cols[1]:
        new_win_criteria_v = st.selectbox("Sets",
            list(CRITERIA.values()),
            format_func = lambda o: o.title(),
            )
        new_winning_score = st.number_input("Play Set to", value=25)
        new_last_set_score = st.number_input("Last Set Score", value=15)
        st.subheader("")
            
        #st.write("")
    if st.button("➕ Add Match"):
        try:
            new_match_type = [k for k, v in MATCH_TYPE.items() if new_match_type_v in v][0]
            new_set_rules = [k for k, v in NUM_PLAYERS.items() if new_set_rules_v == v][0]
            new_win_criteria = [k for k, v in CRITERIA.items() if new_win_criteria_v in v][0]
            with sqlite3.connect(DB_FILE) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO Schedule (match_date, match_time, us_team_id, them_team_id, match_type, match_location, set_rules, win_criteria, winning_score, last_set_score)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (new_match_date,
                      new_match_time,
                      int(st.session_state.us_team_id),
                      int(them_team_id),
                      int(new_match_type), 
                      new_match_location,
                      int(new_set_rules),
                      int(new_win_criteria),
                      int(new_winning_score),
                      int(new_last_set_score)
                ))
                conn.commit()
        except Exception as e:
            st.error(f"Failed to add match: {e}")
            st.write()
        st.success("Match added to schedule.")
        st.cache_data.clear()
        df_schedule = load_schedule_from_database(df_teams.index.tolist())
    st.markdown("---")    
    return df_schedule

def assign_starting_lineup(roster: pd.DataFrame) -> None:
    roster = roster[roster["team_id"]==st.session_state.us_team_id]
    liberos = roster[roster["player_abbv_position"] == "L"]["player_jersey"].tolist()
    st.session_state.liberos = liberos[:2]
    role_map = {1: "S", 2: "OH", 3: "M", 4: "RS", 5: "OH", 6: "M"}
    st.session_state.roster = dict(zip(roster["player_jersey"], roster["player_name"]))
    st.session_state.player_ids = dict(zip(roster["player_jersey"], roster.index))
    team_size = int(NUM_PLAYERS[st.session_state.match["set_rules"]])
    assigned = []
    for i in range(1, team_size+1):
        #TODO add a "player_starter" column to table in db and roster
        # enabling user to identify role 1 to 6, use below code as fallback
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

def get_player_rotation() -> Tuple[list, list]:
    """
    returns two lists of integers
    list is rotation positions based on team size and current rotation value
    """
    r = st.session_state.rotation
    team_size = int(NUM_PLAYERS[st.session_state.match["set_rules"]])

    if team_size == 6:
        front_row = [(i % 6 + 1) for i in range(2 + r, r - 1, -1)]
        back_row = [(i % 6 + 1) for i in range(r + 3, r + 5)] + [(r - 1) % 6 + 1]
    elif team_size == 4:
        front_row = [(i % 4 + 1) for i in range(1 + r, r - 1, -1)]
        back_row = [(i % 4 + 1) for i in range(r + 2, r + 3)] + [(r - 1) % 4 + 1]
    elif team_size == 3:
        front_row = [(i % 3 + 1) for i in range(1 + r, r - 1, -1)]
        back_row = [(r+2) % 3 + 1] 
    elif team_size == 2:
        front_row = [2] if r == 1 else [1]
        back_row = [1] if r == 1 else [2]
    else:                                                                                                                                                                                            
        st.error(f"Unrecognized Team Size: {team_size}")
        return [], []
    return front_row , back_row

# --- Debugging Page ---------------------------------------------------------
with tabs[2]:

    for i in [MATCH_TYPE, NUM_PLAYERS, CRITERIA, TOUCH_TYPE, RESULT, QUALITY]:
        st.write(i)
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
        available_team_ids = df_roster["team_id"].unique() # only teams with rosters are available for our team
        available_teams = df_teams[df_teams.index.isin(available_team_ids)]
        selected_abbr = st.selectbox("Select Team", available_teams["team_abbv"])
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
    
    #TODO make this line pink
    st.markdown("---")
    available_match_ids = show_matches(df_schedule, df_teams)
    if available_match_ids is None:
        st.info("No scheduled matches")
    else:
        selected_match_id = st.selectbox("Select Match", available_match_ids.keys(), index=None)
        if selected_match_id is not None:
            if st.button("🏐 Select Match!"):
                initialize_match(available_match_ids[selected_match_id], df_schedule)
                assign_starting_lineup(df_roster)
                opponent_abbr = df_teams.loc[st.session_state.them_team_id, "team_abbv"]
                st.success(f"Selected match against {opponent_abbr} on {st.session_state.match['match_date']}")

# -----------------------------------------------------------------------------
# Game Tracking
# -----------------------------------------------------------------------------
# --- Helper Utilities ---

def display_scoreboard(match_teams: List[str]) -> None:
    # show header with teams and scores
    header_col = st.columns([1, 3, 1])
    with header_col[0]:
        st.metric(f"Sets Us: {st.session_state.sets_us}",
            st.session_state.score_us)
    with header_col[1]:
        ### TODO center align
        st.subheader(f"{match_teams[0]}   vs   {match_teams[1]}")
    with header_col[2]:
        st.metric(f"Sets Them: {st.session_state.sets_them}",
            st.session_state.score_them)        
    return

def start_set(match_teams: List[str]) -> None:
    # at start of set - user assigns first rotation, and first serve
    st.markdown("---")
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
    ### TODO confirm liberos (up to 2) - default display based on positions
    # at start of set - reset rally, possession, points to win
    player_options = list(st.session_state.roster.keys())
    # user assigns players
    for i in range(2):
        try:
            idx = st.session_state.libero[i]
        except:
            idx = None
        idx = player_options.index(st.session_state.libero[i])

    new_player = start_col[0].selectbox(f"Libero 1",
            player_options,
            format_func = lambda o: f"# {o} {st.session_state.roster[o]}",
            index=idx
            )
        if new_player:
            st.session_state.lineup[key] = int(new_player)

    st.write(st.session_state.liberos)
    st.session_state.subs = 15
    st.session_state.to = 2
    st.session_state.rally_id = 0
    st.session_state.possession_id = 0 if first_serve == match_teams[0] else 1
    def _get_play_to_points() -> int:
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
    st.session_state.points_to_win = _get_play_to_points()
    # draw a "net" line
    # TODO make line pink
    st.markdown("---")
    # layout players below net based on set_rules
    if int(NUM_PLAYERS[st.session_state.match["set_rules"]]) == 6:
        players_col = st.columns(3)
    else: 
        players_col = st.columns(2)
    
    front_row, back_row = get_player_rotation()
    # user assigns players
    for i, key in enumerate(front_row):
        idx = player_options.index(st.session_state.lineup[key])
        new_player = players_col[i].selectbox(f"Front rotation {key}",
            player_options,
            format_func = lambda o: f"# {o} {st.session_state.roster[o]}",
            index=idx
            )
        if new_player:
            st.session_state.lineup[key] = int(new_player)
    for i, key in enumerate(back_row):
        idx = player_options.index(st.session_state.lineup[key])
        if len(back_row) == 1: i = 1
        new_player = players_col[i].selectbox(f"Back rotation {key}",
            player_options,
            format_func = lambda o: f"# {o} {st.session_state.roster[o]}",
            index=idx
            )
        if new_player:
            st.session_state.lineup[key] = int(new_player)

    def _validate_lineup(roster: pd.DataFrame) -> bool:
        """Validate current lineup. If team omitted, infer from current_match."""
        team_size = int(NUM_PLAYERS[st.session_state.match["set_rules"]])
        jerseys = list(st.session_state.lineup.values())
        ### check for no nulls or duplicates
        if None in jerseys or len(jerseys) != team_size or len(set(jerseys)) != team_size:
            return False
        ### confirm all jerseys are on us_team_id
        roster = roster[roster['team_id']==st.session_state.us_team_id]
        team_jerseys = roster['player_jersey'].to_list()
        return all(j in team_jerseys for j in jerseys)

    if not _validate_lineup(df_roster):
        st.error("Invalid Lineup")
    else:
        if st.button(f"🏐 Start Set #{st.session_state.set_id}"):
            st.session_state.active_set = True            
            st.rerun()

def display_lineup() -> None:
    #TODO update next line to show numbers in pink
    st.write(f"-- Current Rotation: {st.session_state.rotation}" +
        f" -- Subsitutions Remaining: {st.session_state.subs}" +
        f" -- Timeouts Remaining: {st.session_state.to} --")
    st.markdown("---")
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

def over_net() -> None:
    """increments the rally_step tracker"""
    st.session_state.possession_id += 2
    st.session_state.defend = False

def log_touch(jersey: int, seq:int, touch:int, result:int, quality:int=None) -> None:
    row = len(st.session_state.touch_log_df)
    touch = {
        'match_id': st.session_state.match_id,
        'set_id': st.session_state.set_id,
        'rally_id': st.session_state.rally_id,
        'possession_seq': st.session_state.possession_id,
        'touch_seq': seq,
        'player_id': st.session_state.player_ids[jersey],
        'touch_type': touch,
        'touch_result': result,
        'touch_quality': quality,
        }
    st.session_state.touch_log_df.loc[row] = touch

def log_rally_start() -> None:
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
        "rotation" : st.session_state.rotation,
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
    initialize_rally()
    return    

def log_set_over() -> None:
    row = len(st.session_state.set_score_log_df)
    score = {
        "match_id": st.session_state.match_id,
        "set_id" : st.session_state.set_id,
        "points_us" : st.session_state.score_us,
        "points_them" : st.session_state.score_them,
    }
    st.session_state.rally_log_df.loc[row] = score

def log_game_over() -> None:
    #TODO append set_score_log_df to Log_SetScores Table in database
    #TODO append rally_log_df to Log_Rally Table in database
    #TODO append rotation_log_df to Log_Rotation Table in database
    #TODO append to touch_log_df to Log_Touch Table in database
    #TODO update Schedule Table in database to reflect match complete
    pass

def score_point(us:bool=True) -> None:
    
    def _check_for_win() -> bool:
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
        
    def _start_new_set() -> None:
        log_set_over()
        st.session_state.game_over = _check_for_win()
        if st.session_state.game_over == False:
            st.session_state.active_set = False
            st.session_state.score_us = 0
            st.session_state.score_them = 0
            st.session_state.set_id += 1

    st.session_state.rally_id += 1
    st.session_state.defend = False
    if us:
        st.session_state.score_us += 1
        if st.session_state.possession_id % 2 == 1:
            st.session_state.rotation = (st.session_state.rotation + 1) % NUM_PLAYERS[st.session_state.match["set_rules"]]
        st.session_state.possession_id = 0
        if (
            st.session_state.score_us >= st.session_state.points_to_win
            and st.session_state.score_us
            >= st.session_state.score_them + 2
        ):
            st.session_state.sets_us += 1
            _start_new_set()
    else:
        st.session_state.score_them += 1
        st.session_state.possession_id = 1

        if (
            st.session_state.score_them >= st.session_state.points_to_win
            and st.session_state.score_them
            >= st.session_state.score_us + 2
        ):
            st.session_state.sets_them += 1
            _start_new_set()
    pass

def our_serve() -> None:
    #identify server
    _, back_row = get_player_rotation()
    server = st.session_state.lineup[back_row[-1]]
    st.markdown(f"#### #{server} {st.session_state.roster[server]} to serve:")
    serve_col = st.columns(2)

    #identify result of serve
    key = next(k for k, v in TOUCH_TYPE.items() if v == 'SERVE')
    options = [i for i in range(key+1, key+9) if i in RESULT.keys()]
    result_serve = serve_col[0].radio("Serve result:", 
        options,
        label_visibility="collapsed",
        format_func = lambda o: RESULT[o].title(),
        horizontal=False)
    #record serve and update game state
    if serve_col[1].button("Record Serve"):
        log_touch(server, 0, 0, result_serve)
        log_rally_start()
        if RESULT[result_serve].upper() == "ACE":
            score_point(True)
        elif "ERROR" in RESULT[result_serve].upper():
            score_point(False)
        else:
            over_net()
        st.rerun()

def opponent_play() -> bool:
    opp_play = "Serve" if st.session_state.possession_id == 1 else "Volley"
    st.markdown(f"#### {match_teams[1]} to {opp_play}:")

    opponent_col = st.columns(2)
    if opp_play.upper() == "SERVE":
        options = ["Serve/In Play", "Serve - Error"]
    else:
        options = ["Attack/In Play", "Attack/Defend - Error"]
    
    opponent_result = opponent_col[0].radio(
        f"{opp_play} result:",
        options,
        label_visibility="collapsed",
        horizontal=True)
    
    if opponent_col[1].button(f"Record {match_teams[1]}"):
        if "SERVE" in opponent_result.upper():
            log_rally_start()
        if "ERROR" in opponent_result.upper():
            score_point(True)
            st.session_state.defend = False
            st.rerun()
        else: 
            st.session_state.defend = True
            st.rerun()

def our_play() -> None:
    def _our_block()->Tuple[List[int], int]:
        #identify blockers
        front_row, _ = get_player_rotation()
        blocker_options = [st.session_state.lineup[key] for key in front_row]
        blockers = st.pills("Blockers", 
            blocker_options,
            selection_mode="multi", default=None,
            format_func=lambda o: st.session_state.roster[o], 
        )
        #identify result of block
        key = next(k for k, v in TOUCH_TYPE.items() if v == 'BLOCK')
        result_options = [i for i in range(key+1, key+9) if i in RESULT.keys()]
        if len(blockers) == 2: 
            result_options = [i for i in result_options if "ASSIST" in RESULT[i]]
        if len(blockers) > 2:
            st.warning("too many blockers")
            result_block = None
        else:
            result_block = st.radio("Block result:", 
                result_options,
                format_func = lambda o: RESULT[o].title(),
                horizontal=False)
        #return blockers and result
        #blockers = blockers[:2] if "ASSIST" in RESULT[result_block].upper() else blockers[:1]
        return blockers, result_block        
        
    def _our_touch(touch:int)->Tuple[int, int, int]:
        #identify players
        player = st.pills(f"Player {touch}:", 
            list(st.session_state.lineup.values()),
            selection_mode="single", default=None,
            format_func=lambda o: st.session_state.roster[o], 
        )
        touch_options = [60, 10, 20, 30, 70] if touch == 1 else [10, 20, 30]
        key = st.pills(f"Touch {touch}:", 
            touch_options,
            selection_mode="single", 
            default= 10 * touch,
            format_func=lambda o: TOUCH_TYPE[o].title()
        )
        if key == 70: player = 99
        result_options = [i for i in range(key+1, key+9) if i in RESULT.keys()]
        result = st.radio(f"Result {touch}:", 
            result_options,
            format_func = lambda o: RESULT[o].title(),
            index = None,
            horizontal=False)
        #record block and update game state
        return player, key, result

    players = []
    seqs = []
    touches = []
    results = []
    t = "Serve-Receive" if st.session_state.possession_id==1 else "Defend-to-Attack"
    st.markdown(f"#### {t}:")
    # check for block
    if st.session_state.possession_id != 1:
        if st.toggle("Block?", on_change=None):
            st.markdown(f"#### Block:")
            blockers, result_block = _our_block()
            if None not in [blockers, result_block]:
                if ("STUFF" in RESULT[result_block].upper()) or ("ERROR" in RESULT[result_block].upper()) or ("BLOCK" in RESULT[result_block].upper()):
                    seq = 4
                    cols = st.columns(2)
                    if cols[1].button("Record Block"):
                        for b in blockers: 
                            log_touch(b, seq, 40, result_block)
                            seq+=1
                        if "STUFF" in RESULT[result_block].upper():
                            score_point(True)
                        elif "ERROR" in RESULT[result_block].upper():
                            score_point(False)
                        elif "BLOCK" in RESULT[result_block].upper():
                            over_net()
                        st.rerun()
                players.append(blockers[0])
                seqs.append(4)
                touches.append(40)
                results.append(result_block)

    for t in range(1,4):
        player, touch, result = None, None, None
        st.markdown("---")
        st.markdown(f"#### Touch #{t}:")
        player, touch, result = _our_touch(t)
        players.append(player)
        seqs.append(t)
        touches.append(touch)
        results.append(result)
        if None not in [player, touch, result]:
            if ("KILL" in RESULT[result].upper()) or ("ERROR" in RESULT[result].upper()) or ("OVER" in RESULT[result].upper()):
            #TODO update to escape for loop when button is shown
                cols = st.columns(2)
                if cols[1].button("Record Volley"):
                    for i in range(len(players)): 
                        ### assign team error touch to all players
                        if touches[i] == 70:
                            for p in list(st.session_state.lineup.values()):
                                log_touch(p, seqs[i], touches[i], results[i])
                        else:
                            log_touch(players[i], seqs[i], touches[i], results[i])
                    if "KILL" in RESULT[result].upper():
                        score_point(True)
                    elif "ERROR" in RESULT[result].upper():
                        score_point(False)
                    elif "OVER" in RESULT[result].upper():
                        over_net()
                    st.rerun()

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
            #TODO don't decrement subs if player going in/out is a libero
            st.session_state.subs += -1
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
                score_point(True)
            elif add_point == match_teams[1]:
                score_point(False)
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
        if st.session_state.active_set == False:
            start_set(match_teams)
        else:
            display_lineup()
        st.markdown("---")

        # if game is over - take end of game actions
        if st.session_state.game_over == True:
            #TODO - mark game as complete
            #TODO - store dfs in database
            display_game_over()

        elif st.session_state.active_set == True:
            # if game is NOT over and it's our serve -
            if st.session_state.possession_id == 0:
                our_serve()
            elif st.session_state.defend:
                our_play()
            else:
                opponent_play()    
        
            #TODO determine appropriate display for deadball actions
            if st.session_state.possession_id < 2:
               if st.checkbox("Dead Ball Actions:", value=False):
                    display_dead_ball()
            else:
                if st.checkbox("Whistle Actions:", value=False):
                    display_live_ball()
