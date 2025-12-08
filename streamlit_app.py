"""
A Streamlit app for volleyball stat collection and tracking.
Developed by Robert Patchin with assistance from ChatGPT and Bing Co-Pilot.
"""
# -----------------------------------------------------------------------------
# import libraries 
# -----------------------------------------------------------------------------

import pandas as pd
import streamlit as st

import sqlite3

import re
from datetime import datetime, date
from zoneinfo import ZoneInfo

from dataclasses import asdict, dataclass
from typing import Optional, TypedDict, List, cast

from typing import Tuple
from functools import cache

from collections import Counter


# -----------------------------------------------------------------------------
# class declarations
# -----------------------------------------------------------------------------

@dataclass
class Team(TypedDict):
    team_id: int
    team_name: str
    team_abbv: str
    season: str
    club: Optional[str] = None
    team_hometown: Optional[str] = None
    team_coach: Optional[str] = None

class Player(TypedDict):
    player_id: int
    player_name: str
    player_jersey: int
    player_team: int
    position: Optional[str] = None

class TouchLog:
    """
    Data class representing a single touch in a possession
    """
    touch_seq: int
    touch_id: int
    touch_type: int
    touch_result: int
    touch_quality: int


# -----------------------------------------------------------------------------
# Global Constants and Session State Initialization
# -----------------------------------------------------------------------------

@cache
def load_data_from_database(season: str, db_path: str = "OP_VBC.db") -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict, dict, dict, dict, dict, dict]:
    """Load Teams, Player_Roster, and Matches from the OP_VBC SQLite DB.
    - Filters Teams by season.
    - Loads rosters for those teams.
    - Loads incomplete matches for those teams.
    - Loads dictionaries to describe matches and touches 
    Returns three dataframes and six dictionaries in the order: teams, rosters, matches, touch_types, results, quality, match_types, rules, criteria
    If the DB is missing or tables are not present, returns empty dataframes with sensible columns and empty dictionaries.
    """
    # empty dataframes as fallback
    df_teams = pd.DataFrame(columns=["team_id", "team_name", "team_abbv", "club", "season"])
    df_rosters = pd.DataFrame(columns=["player_id", "player_name", "player_jersey", "player_position", "player_team"])
    df_matches = pd.DataFrame(columns=["match_id", "match_date", "us_team_id", "them_team_id",
                                       "match_type", "match_location", "set_rules", "player_rules",
                                       "winning_score", "last_set_score", "match_complete"])
    touch_types = {}
    touch_results = {}
    touch_quality = {}

    match_types = {}
    match_rules = {}
    match_criteria = {}

    try:
        with sqlite3.connect(db_path) as conn:
            # Load Dictionaries from lookup tables
            df = pd.read_sql_query("SELECT * FROM Touch_Types", conn)
            touch_types = {row["type_id"]: row["touch_type"] for _, row in df.iterrows()}

            df = pd.read_sql_query("SELECT * FROM Touch_Results", conn)
            touch_results = {row["result_id"]: row["touch_result"] for _, row in df.iterrows()}

            df = pd.read_sql_query("SELECT * FROM Touch_Qualities", conn)
            touch_quality = {row["quality_id"]: row["quality_description"] for _, row in df.iterrows()}

            df = pd.read_sql_query("SELECT * FROM Match_Types", conn)
            match_rules = {row["type_id"]: row["match_type"] for _, row in df.iterrows()}

            df = pd.read_sql_query("SELECT * FROM Match_Rules", conn)
            match_rules = {row["rule_id"]: row["rule_description"] for _, row in df.iterrows()}

            df = pd.read_sql_query("SELECT * FROM Match_Criteria", conn)
            match_rules = {row["criteria_id"]: row["criteria_description"] for _, row in df.iterrows()}

            # Load Teams from the specified season
            q = "SELECT * FROM Teams WHERE season = ?"
            df_teams = pd.read_sql_query(q, conn, params=(season,))
            if df_teams.empty:
                return df_teams, df_rosters, df_matches, touch_types, touch_results, touch_quality, match_types, match_rules, match_criteria

            team_ids = df_teams["team_id"].unique().tolist()
            t_placeholders = ",".join(["?"] * len(team_ids))

            # Load Player_Roster for those teams
            q = f"SELECT * FROM Rosters WHERE player_team IN ({t_placeholders})"
            df_rosters = pd.read_sql_query(q, conn, params=team_ids)

            # Load incomplete Matches for those teams
            q = f"SELECT * FROM Matches WHERE us_team_id IN ({t_placeholders}) AND match_complete = 0"
            df_matches = pd.read_sql_query(q, conn, params=team_ids)

            if not df_matches.empty and "match_date" in df_matches.columns:
                df_matches["match_date"] = pd.to_datetime(df_matches["match_date"], errors="coerce")
                df_matches = df_matches.sort_values("match_date")

    except sqlite3.Error as e:
        print(f"SQLite error: {e}")

    return df_teams, df_rosters, df_matches, touch_types, touch_results, touch_quality, match_types, match_rules, match_criteria


def initialize_state() -> None:
    """
    Initialize session state variables.
    """
    if "game_over" not in st.session_state:
        st.session_state.game_over = False
    if "sets_us" not in st.session_state:
        st.session_state.sets_us = 0
    if "sets_them" not in st.session_state:
        st.session_state.sets_them = 0
    if "current_match" not in st.session_state:
        st.session_state.current_match = None
    if "current_set" not in st.session_state:
        st.session_state.current_set = 1
    if "current_rally" not in st.session_state:
        st.session_state.current_rally = 0
    if "current_poss" not in st.session_state:
        st.session_state.current_poss = 0
    if "points_us" not in st.session_state:
        st.session_state.score_us = 0
    if "points_them" not in st.session_state:
        st.session_state.score_them = 0
    if "rotation" not in st.session_state:
        st.session_state.rotation = 1
    if "rally_step" not in st.session_state:
        LA_time = datetime.now(ZoneInfo("America/Los_Angeles")).strftime("%H:%M:%S")
        st.session_state.rally_step = {
          "sanctions": "",
          "remarks": "",
          "serve_timestamp": LA_time
        }
    if "lineup" not in st.session_state:
        st.session_state.lineup = {}
    if "touch_log" not in st.session_state:
        st.session_state.touch_log ={}
    if "match_sets_df" not in st.session_state:
        st.session_state.match_sets_df = pd.DataFrame()
    if "rally_log_df" not in st.session_state:
        st.session_state.rally_log_df = pd.DataFrame()
    if "rally_players_df" not in st.session_state:
        st.session_state.rally_players_df = pd.DataFrame()
    if "touch_log_df" not in st.session_state:
        st.session_state.touch_log_df = pd.DataFrame()

DB_FILE = "OP_VBC.db"
SEASON = '2025 Club'
df_teams, df_rosters, df_matches, TOUCH_TYPES, TOUCH_RESULTS, TOUCH_QUALITY, MATCH_TYPE, MATCH_RULES, MATCH_CRITERIA = load_data_from_database(SEASON, DB_FILE)
initialize_state()

# -----------------------------------------------------------------------------
# U/I configuration
# -----------------------------------------------------------------------------
st.set_page_config(page_title="VStat",
                   layout="wide",
                   page_icon=":volleyball:")
st.title("🏐 VolleyStat")

tabs = st.tabs([
    "Schedule",
    "Live Track",
])


# -----------------------------------------------------------------------------
# Scheduling
# -----------------------------------------------------------------------------
# --- Helper Utilities ---
def show_schedule(
    df_matches: pd.DataFrame = df_matches,
    df_teams: pd.DataFrame = df_teams):

    us_team = df_teams.loc[
        df_teams['team_name'] == st.session_state.my_team_selected, 'team_id'
    ].iloc[0]
    df = df_matches[df_matches['us_team_id'] == us_team]
    df["match_type"] = df["match_type"].map(MATCH_TYPE.get)
    df["set_rules"] = df["set_rules"].map(MATCH_RULES.get)
    df["win_criteria"] = df["win_criteria"].map(MATCH_CRITERIA.get)
    df["match_date"] = pd.to_datetime(df["match_date"]).dt.strftime("%Y-%m-%d")
    df = df.merge(df_teams, left_on="them_team_id", right_on="team_id", suffixes=("", "_opponent"))
    columns = ["match_id", "match_date", "team_abbv",
               "match_location", "match_type",
                "set_rules", "win_criteria",
                "winning_score", "last_set_score"]
    df = df[columns]

    selected = st.dataframe(
        df,
        hide_index=True,
#        on_selection="rerun",
        selection_mode='single-row',
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

    st.write("Select Match")




def assign_default_lineup(team: Team) -> None:
#    players = sorted(team["players"], key=lambda p: p["jersey"])[:6]
#    for i in range(1, 7):
#        jersey = players[i - 1]["jersey"] if i <= len(players) else i
#        st.session_state.lineup[f"position_{i}"] = jersey
    role_map = {
        "S": 1,
        "DS": 2,
        "MB": [3, 6],
        "RS": 4,
        "OH": 5,
    }
    assigned = {}
    for p in sorted(team["players"], key=lambda p: p["jersey"]):
        pos = role_map.get(p["position"], None)
        if isinstance(pos, list):
            for i in pos:
                if i not in assigned:
                    assigned[i] = p["jersey"]
                    break
        elif pos and pos not in assigned:
            assigned[pos] = p["jersey"]
    for i in range(1, 7):
        st.session_state.lineup[f"position_{i}"] = assigned.get(i, i)



st.markdown("---")
if st.session_state.current_match:
    st.warning("A match is in progress. Starting a new one will overwrite it.")

team_options = df_teams['team_name']
st.selectbox("Select Team", team_options, index=0, key='my_team_selected', disabled = True)

#st.write(st.session_state.my_team_selected)


st.subheader("Upcoming Matches")
show_schedule()

# --- Scheduling Page ---------------------------------------------------------
with tabs[1]:
    st.markdown("---")
    if st.session_state.current_match:
        st.warning("A match is already in progress. Starting a new one will overwrite it.")
    st.subheader("Upcoming Matches")
    st.dataframe(df_matches)



# -----------------------------------------------------------------------------
# Game Tracking
# -----------------------------------------------------------------------------
# --- Helper Utilities ---
def get_play_to_points() -> int:
    """uses set format and current set to deterimine point to win
    returns: int, min points to win"""
    if st.session_state.current_match['set_format'] == "Best of 5":
        if st.session_state.current_set == 5:
            return st.session_state.current_match['last_set_points']
        else:
            return st.session_state.current_match['points_to_win']
    else:
        if st.session_state.current_set == 3:
            return st.session_state.current_match['last_set_points']
        else:
            return st.session_state.current_match['points_to_win']

def check_for_win() -> bool:
    """ evalutes set state and logic
    returns True if match is complete, otherwise False
    """
    if st.session_state.current_match['set_format'] == "Best of 5":
        if max(st.session_state.score_us, 
               st.session_state.score_them) == 3:
            return True
        else: return False
    elif st.session_state.current_match['set_format'] == "Best of 3":
        if max(st.session_state.score_us, 
               st.session_state.score_them) == 2:
            return True
        else: return False
    else: 
        if st.session_state.current_set == 3:
            return True
        else: return False

def get_player_rotation() -> list:
    """
    returns list of integers
    list is rotation positions based on current rotation value
    """
    r = st.session_state.rotation
    front_row = [(i % 6 + 1) for i in range(2 + r, r - 1, -1)]
    back_row = [(i % 6 + 1) for i in range(r + 3, r + 5)] + [(r - 1) % 6 + 1]
    return front_row + back_row

def add_new_rally_step(rally: RallyStep) -> None:
    """ adds new df row based on current session state """
    index = pd.MultiIndex.from_tuples(
        [(st.session_state.current_match['match_id'],
          st.session_state.current_set,
          st.session_state.score_us,
          st.session_state.score_them,
          st.session_state.rally_step,
        )],
        names=[
            "match_id",
            "set",
            "score_us",
            "score_them",
            "step",
        ])
    st.session_state.game_record_df = pd.concat(
        [st.session_state.game_record_df, pd.DataFrame([asdict(rally)], index=index)],
    )

def point_us() -> None:
    """adds a point to score_us and checks for side-out and set/match win"""
    st.session_state.score_us += 1
    if st.session_state.rally_step % 2 == 1:
        st.session_state.rotation = st.session_state.rotation % 6 + 1
    st.session_state.rally_step = 0

    if (
        st.session_state.score_us >= get_play_to_points()
        and st.session_state.score_us
        >= st.session_state.score_them + 2
    ):
        st.session_state.sets_us += 1
        st.session_state.game_over = check_for_win()
        if st.session_state.game_over == False:
            st.session_state.score_us = 0
            st.session_state.score_them = 0
            st.session_state.current_set += 1

def point_them() -> None:
    """adds a point to score_them and checks for set/match win"""
    st.session_state.score_them += 1
    st.session_state.rally_step = 1

    if (
        st.session_state.score_them >= get_play_to_points()
        and st.session_state.score_them
        >= st.session_state.score_us + 2
    ):
        st.session_state.sets_them += 1
        st.session_state.game_over = check_for_win()
        if st.session_state.game_over == False:
            st.session_state.score_us = 0
            st.session_state.score_them = 0
            st.session_state.current_set += 1

def over_net() -> None:
    """increments the rally_step tracker"""
    st.session_state.rally_step += 2

def undo_last_line() -> None:
    """removes last line of df and resets key session_state conditions"""
    if not st.session_state.game_record_df.empty:
        st.session_state.game_record_df = st.session_state.game_record_df.iloc[:-1]

    if not st.session_state.game_record_df.empty:
        st.session_state.game_over = False
        if st.session_state.current_set != st.session_state.game_record_df.iloc[-1]["set"]:
            if  st.session_state.game_record_df.iloc[-1]['score_us'] > st.session_state.game_record_df.iloc[-1]['score_them']:
                st.session_state.sets_us = max(0, st.session_state.sets_us - 1)
            else:
                st.session_state.sets_them = max(0, st.session_state.sets_them - 1)
            st.session_state.current_set = st.session_state.game_record_df.iloc[-1]["set"]
        st.session_state.score_us = st.session_state.game_record_df.iloc[-1]['score_us']
        st.session_state.score_them = st.session_state.game_record_df.iloc[-1]['score_them']
        st.session_state.rally_step = st.session_state.game_record_df.iloc[-1]['step']
        st.session_state.rotation = st.session_state.game_record_df.iloc[-1]['rotation']
        for i in range(1, 7):
            st.session_state.lineup[f"position_{i}"] = st.session_state.game_record_df.iloc[-1][f"position_{i}"]
    else:
        st.session_state.score_us = 0
        st.session_state.score_them = 0
        st.session_state.rally_step = 0
    st.success("Undid last event")

def volley_outcome(results: List[str], opponent_rally: str) -> str:
    if "Error" in opponent_rally:
        return "us"
    if any(r in results for r in ["Kill", "Ace", "Stuff", "Assist"]):
        return "us"
    if any(r in results for r in ["Error", "Miss", "Tool"]):
        return "them"
    if "Over" in results:
        return "continue"
    return "invalid"

def validate_lineup(team: Optional[Team] = None) -> bool:
    """Validate current lineup. If team omitted, infer from current_match."""
    if team is None:
        if not st.session_state.get("current_match"):
            return False
        team = find_team(st.session_state.current_match.get("our_team", ""))
        if team is None:
            return False

    jerseys = list(st.session_state.lineup.values())
    if None in jerseys or len(jerseys) != 6 or len(set(jerseys)) != 6:
        return False
    team_jerseys = {p["jersey"] for p in team["players"]}
    return all(j in team_jerseys for j in jerseys)

# --- Game Tracking Page ---
with tabs[2]:
    st.header("Game Tracking")
    """
    Game Tracking supports:
        Tracking Score and Sets won
        Input of starting lineup for each set
        Court Aware display of current rotation
        Stat collection by touch
        Tracking sanctions and subsitutions
        Undoing mistakes inputs
        Displaying recent logs
    """
    if not st.session_state.current_match:
        st.info("Start a match from Scheduling to begin tracking")
    else:
        match_teams = [f"{st.session_state.current_match['our_team']}",
                       f"{st.session_state.current_match['opponent']}"]

        left, mid, right = st.columns([1, 3, 1])
        with left:
            st.metric(f"Sets: {st.session_state.sets_us}",
                      st.session_state.score_us)
        with mid:
            st.subheader(f"{match_teams[0]} vs {match_teams[1]}")
        with right:
            st.metric(f"Sets: {st.session_state.sets_them}",
                      st.session_state.score_them)        
        st.markdown("---")

        col1, col2, col3 = st.columns(3)
        cols = [col1, col2, col3]
        front_row, back_row = get_player_rotation()[:3], get_player_rotation()[3:]

        if st.session_state.score_us + st.session_state.score_them == 0 and not st.session_state.game_over:
            st.session_state.rotation = st.sidebar.slider("Rotation",
                                                          min_value=1,
                                                          max_value=6,
                                                          value=1
            )
            for i, p in enumerate(front_row):
                if i == 0: st.write("#### Front Row")
                else: st.write("#### ")
                key = f"position_{p}"
                jersey = st.session_state.lineup[key]
                default_val = 0 if jersey is None else int(jersey)
                new_player = cols[i].number_input(f"Front {p}",
                                                  min_value=0,
                                                  value=default_val,
                                                  key=f"front_{i}")
                if new_player:
                    st.session_state.lineup[key] = int(new_player)

            for i, p in enumerate(back_row):
                if i == 0: st.write("#### Back Row")
                else: st.write("#### ")
                key = f"position_{p}"
                jersey = st.session_state.lineup[key]
                default_val = 0 if jersey is None else int(jersey)
                new_player = cols[i].number_input(f"Back {p}",
                                                    min_value=0,
                                                    value=default_val,
                                                    key=f"back_{i}")
                if new_player:
                    st.session_state.lineup[key] = int(new_player)

            first_serve = st.radio("First to serve:", 
                                   match_teams,
                                   index=0, key=f"fts{st.session_state.current_set}",
                                   horizontal=True)
            st.session_state.rally_step = 0 if first_serve == match_teams[0] else 1
            if not validate_lineup():
                st.error("Invalid Lineup")
        else:
            st.write(f"Current Rotation: {st.session_state.rotation}" +
                     f"   --   Current Volley Index: {st.session_state.rally_step}")
            for i, p in enumerate(front_row):
                key = f"position_{p}"
                with cols[i]:
                    if i == 0: st.write("Front Row")
                    else: st.write("")
                    st.write(st.session_state.lineup[key])
            for i, p in enumerate(back_row):
                key = f"position_{p}"
                with cols[i]:
                    if i == 0: st.write("Back Row")
                    else: st.write("")
                    st.write(st.session_state.lineup[key])

        st.markdown("---")

        if st.session_state.game_over == True:
            match_id = st.session_state.current_match["match_id"]
            final_score = f"{st.session_state.score_us}–{st.session_state.score_them}"
            total_rallies = len(st.session_state.game_record_df)
            st.markdown("### Game Over")
            df = st.session_state.game_record_df.reset_index()
            touches = pd.Series(dtype=int)
            kills = pd.Series(dtype=int)

            for col in ["touch_1", "touch_2", "touch_3"]:
                players = df[col].dropna().apply(lambda x: x.split(":")[0])
                results = df[col].dropna().apply(lambda x: x.split(":")[-1])
                touches = touches.add(players.value_counts(), fill_value=0)
                kills = kills.add(players[results == "Kill"].value_counts(), fill_value=0)

            impact_df = pd.DataFrame({
                "Touches": touches.astype(int),
                "Kills": kills.astype(int)
                }).fillna(0).astype(int).sort_values("Kills", ascending=False)
            st.dataframe(impact_df)

        elif st.session_state.rally_step == 0:
            key = f"position_{get_player_rotation()[-1]}"
            server = st.session_state.lineup[key]
            st.markdown(f"### Player {server} to serve:")
            key = f"{key} + {st.session_state.score_us}"
            resultS = st.radio("Serve result:", 
                                   ["Ace", "Error", "Return"],
                                   key=f"serve{key}",
                                   horizontal=True)
        else:
            resultS = None
            if st.session_state.rally_step == 1:
                st.markdown("### Serve Receive:")
                opponent_rally = st.radio("Serve result:", ["Over", "Error"],
                                   key=f"serveT_{str(st.session_state.score_us)} + {str(st.session_state.score_them)}",
                                   horizontal=True)
            else:
                st.markdown("### Volley to Continue Rally:")
                opponent_rally = st.radio("Volley result:", 
                                   ["Error", "Attack"],
                                   key=f"attack{str(st.session_state.score_us)}" + 
                                       f"{str(st.session_state.score_them)}" +
                                       f"{str(st.session_state.rally_step)}",
                                   horizontal=True)
            b0, c1, c2, c3 = st.columns(4)
            with b0:
                playerA = st.selectbox(
                    "Block - Player",
                    options = list(st.session_state.lineup.values()[:3]) + [None],
                    index=None,
                )
                playerB = st.selectbox(
                    "Block - Player",
                    options = list(st.session_state.lineup.values()[:3]) + [None],
                    index=None,
                )
                resultB = st.selectbox(
                    "Block - Result",
                    options=["Stuff", "Assist", "Block:Over", "Tool", "Error", "Tip:Played", ""],
                    index=4
                )
            with c1:
                player1 = st.selectbox(
                    "Touch 1 - Player",
                    options = list(st.session_state.lineup.values()) + [None],
                    index=None,
                )
                touch1 = st.selectbox(
                    "Touch 1 - Type",
                    ["Dig", "Pass", "Set", "Attack"],
                )
                result1 = st.selectbox(
                    "Touch 1 - Result",
                    ["OK", "Error", "Miss", "Kill", "Over"],
                )
            with c2:
                player2 = st.selectbox(
                    "Touch 2 - Player",
                    options = list(st.session_state.lineup.values()) + [None],
                    index=None,
                )
                touch2 = st.selectbox(
                    "Touch 2 - Type",
                    ["Pass", "Set", "Attack"],
                )
                result2 = st.selectbox(
                    "Touch 2 - Result",
                    ["OK", "Error", "Over", "Kill"],
                )
            with c3:
                player3 = st.selectbox(
                    "Touch 3 - Player",
                    options = list(st.session_state.lineup.values()) + [None],
                    index=None,
                )
                touch3 = st.selectbox(
                    "Touch 3 - Type",
                    ["Pass", "Set", "Attack"],
                )
                result3 = st.selectbox(
                    "Touch 3 - Result",
                    ["Kill", "Over", "Error"],
                )
        
        if st.button("Record Volley"):
            row = RallyStep(
                        **st.session_state.lineup,
                        rotation=st.session_state.rotation,
            )
            if resultS is not None:
                row.serve_touch = f"{server}:{resultS}"
            if resultB == "Assist":
                row.block_touch = f"{playerA}:{playerB}:{resultB}"
            elif resultB is not None and playerA is not None:
                row.block_touch = f"{playerA}:{resultB}"
            if player1 is not None:
                row.touch_1 = f"{player1}:{touch1}:{result1}"
            if player2 is not None:
                row.touch_2 = f"{player2}:{touch2}:{result2}"
            if player3 is not None:
                row.touch_3 = f"{player3}:{touch3}:{result3}"
            
            add_new_rally_step(row)
            
            results = [resultB, result1, result2, result3]
            outcome = rally_outcome(results, opponent_rally)
            if outcome == "us": point_us()
            elif outcome == "them": point_them()
            elif outcome == "continue": over_net()
            else: st.error("Enter valid rally result")

            st.success("Rally recorded")
        
        st.markdown("---")
        st.markdown("### Deadball Actions")
        c11, c21, c31 = st.columns(3)

        with c11:
            sanctions = st.text_input("Sanctions:", "")
            add_point = st.radio("Add point:", 
                                 [None]+match_teams,
                                 index=0, key=f"sanction_pt{st.session_state.current_set}",
                                 horizontal=False)
            if st.button("Record Sanction"):
                row = RallyStep(
                        **st.session_state.lineup,
                        rotation=st.session_state.rotation)
                if sanctions is not None:
                    row.sanctions = sanctions
                if add_point == match_teams[0]:
                    point_us()
                    add_new_rally_step(row)
                elif add_point == match_teams[1]:
                    point_them()
                    add_new_rally_step(row)
                else:
                    if not st.session_state.game_record_df.empty:
                        last_index = st.session_state.game_record_df.index[-1]
                        st.session_state.game_record_df.at[last_index, "sanctions"] = sanctions

        with c21:
            team_obj = find_team(match_teams[0])
            roster = [p["jersey"] for p in team_obj["players"]] if team_obj else []
            sub_out = st.selectbox("Sub Out", options=list(st.session_state.lineup.values()))
            sub_in = st.selectbox("Sub In", options=[j for j in roster if j not in st.session_state.lineup.values()])
            if st.button("Record Sub"):
                for key, val in st.session_state.lineup.items():
                    if val == sub_out:
                        st.session_state.lineup[key] = sub_in
                        st.success(f"Subbed out {sub_out} for {sub_in}")
                        break

        with c31:
            if st.button("Undo Last"):
                undo_last_line()
        
        st.markdown("---")
        st.markdown("### Live Event Log")
        st.dataframe(st.session_state.game_record_df.tail(5),
                     use_container_width=True)


