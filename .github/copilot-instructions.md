# AI Agent Instructions for VB_scorekeeper

  ## Project Overview
  VolleyStat is a web application for COLLECTING volleyball player statistics on one team at the touch-to-touch level, in real-time.

  To support this, the app must minimize user input requirements while maintaining data accuracy and completeness. 
  
  The app must be game aware, understanding volleyball rules and player rotations to support prompting the user only for necessary inputs. The game log files must be structured and exportable to support post-game analysis. 
  
  The app will be run on tablets or phones during games and screen layout must be optimized for quick access, minimal navigation, and intuitive game flow. Team/Player management and statistical analysis functions will be handled in a separate application. 

  ## Data Model
  - **Persistent Records** are stored in tables in a sqlite database with schema:
      CREATE TABLE Teams (
          team_id INTEGER PRIMARY KEY AUTOINCREMENT,
          team_name TEXT NOT NULL,
          team_abbv TEXT NOT NULL,
          season CHECK(season BETWEEN 25 AND 50),
          club TEXT,
          hometown TEXT,
          coach TEXT,
          UNIQUE(team_name, season),
          UNIQUE(team_abbv, season)
      );
    - 1. The Teams table stores team metadata and enables mapping human readable (team_name and team_abbv) team names to team_id. Adding new teams throughout the season is important as tournament seeding and schedules are often unknown at the start of the season. VolleyStat must be able to load teams from the db table and add new teams to the db table.

      CREATE TABLE Roster (
          player_id INTEGER PRIMARY KEY AUTOINCREMENT,
          player_name TEXT NOT NULL,
          player_last_name TEXT,
          player_jersey INTEGER NOT NULL CHECK(player_jersey BETWEEN 0 AND 99),
          position_id INTEGER,
          team_id INTEGER NOT NULL,
          player_captain BOOL DEFAULT FALSE,
          starter INTEGER DEFAULT 0,
          FOREIGN KEY (team_id) REFERENCES Teams(team_id), 
          FOREIGN KEY (position_id) REFERENCES Positions(position_id), 
          UNIQUE(team_id, player_jersey),
          UNIQUE(player_name, player_last_name)
      )
      CREATE TABLE Positions (
        position_id INTEGER PRIMARY KEY AUTOINCREMENT,
        position_name TEXT NOT NULL,
        position_abbv TEXT NOT NULL
      );
      INSERT INTO Positions (position_name, position_abbv) VALUES
        ("setter", 'S'),
        ("outside hitter", 'OH'),
        ("middle blocker", 'M'),
        ("rightside hitter", 'RS'),
        ("opposite hitter", 'OP'),
        ("serve specialist", 'SS'),
        ("defensive specialist", 'DS'),
        ("libero", 'L'),
        ("utility", 'U');

    - 2. The Roster table stores players on our teams (not opponent teams) - tracking players on opponent teams is neither required nor desired. This table enables mapping human readable labels (player_name, player_jersey) to player_id for players on our teams. Player position may be used in some prompts, but coaches can change player assignments from set to set, so it is NOT constraining. Roster will generally be static throughout the season, with few changes. Any need to update/modify can be handeled in a separate management application. A Positions lookup table is loaded as a dictionary and enables mapping multiple display options for a position. This table is static and should only be updated by the app developer.

      CREATE TABLE Schedule (
          match_id INTEGER PRIMARY KEY AUTOINCREMENT,
          match_date DATE,
          match_time TIME,
          us_team_id INTEGER,
          them_team_id INTEGER,
          match_type INTEGER,
          match_location TEXT, 
          set_rules INTEGER,
          win_criteria INTEGER,
          winning_score INTEGER DEFAULT 25,
          last_set_score INTEGER DEFAULT 15,
          match_complete BOOL DEFAULT FALSE,
          FOREIGN KEY (us_team_id) REFERENCES Teams(team_id),
          FOREIGN KEY (them_team_id) REFERENCES Teams(team_id),
          FOREIGN KEY (match_type) REFERENCES Match_Types(type_id),
          FOREIGN KEY (set_rules) REFERENCES Match_Rules(rule_id),
          FOREIGN KEY (win_criteria) REFERENCES Match_Criteria(criteria_id)
      )
    - 3. The Schedule table stores the schedule for our teams. This table enables tracking each match and the associated match rules. Adding new matches is important throughout the season. An entry in the Schedule table is required prior to data collection. VolleyStat must be able to load scheduled Matches, add new Matches to the schedule, and update Matches when completed.

      CREATE TABLE Match_Types(
	        type_id INTEGER PRIMARY KEY AUTOINCREMENT,
	        match_type TEXT UNIQUE NOT NULL
      );
      INSERT INTO Match_Types (type_id, match_type) VALUES
        (5,	'league'),
        (3,	'tournament'),
        (1,	'scrimmage');

      CREATE TABLE Match_Rules (
          rule_id INTEGER PRIMARY KEY AUTOINCREMENT,
          rule_surface TEXT,
          rule_size INT NOT NULL,
          rule_description TEXT,
          UNIQUE (rule_surface, rule_size, rule_description)
      );
      INSERT INTO Match_Rules (rule_surface, rule_size) VALUES
        ('court', 6),
        ('beach', 2),
        ('grass', 3),
        ('court', 4);

      CREATE TABLE Match_Criteria(
          criteria_id INTEGER PRIMARY KEY,
          criteria_description TEXT UNIQUE NOT NULL
      );
      INSERT INTO Match_Criteria (criteria_id, criteria_description) VALUES
        (2, 'best of 3'),
        (3, '3 sets'),
        (5, 'best of 5'),
        (1, 'single set');

    - 4. Match_Types, Match_Rules, and Match_Criteria lookup tables are loaded as dictionaries and enable us to set the type, rules, and victory criteria for each match. These tables are static and should only be updated by the app developer.

      CREATE TABLE Touch_Seq (
        touch_seq INTEGER PRIMARY KEY,
        touch_sequence TEXT NOT NULL
      );
      INSERT INTO Touch_Seq (touch_seq, touch_sequence) VALUES
            (0, 'SERVE'), 
            (1, 'ONE'),
            (2, 'TWO'),
            (3, 'THREE'),
            (4, 'BLOCK'),
            (5, 'BLOCK');

      CREATE TABLE Touch_Types (
        type_id INTEGER PRIMARY KEY,
        touch_type TEXT UNIQUE NOT NULL
      );
      INSERT INTO Touch_Types (type_id, touch_type) VALUES
        (0, 'SERVE'),
        (10, 'PASS'),
        (20, 'SET'),
        (30, 'ATTACK'),
        (40, 'BLOCK'),
        (60, 'DIG'),
        (70, 'TEAM_ERROR');
      
      CREATE TABLE Touch_Results (
        result_id INTEGER PRIMARY KEY,
        touch_result TEXT NOT NULL
      );
      INSERT INTO Touch_Results (result_id, touch_result) VALUES
        (0, 'ZERO'),
        (1, 'OVER - IN PLAY'),
        (5, 'ACE'),
        (6, 'ERROR - SHORT'),
        (7, 'ERROR - OUT OF BOUNDS'),
        (8, 'ERROR - FAULT'),
    		(9, 'ERROR'),        
		    (10, 'ZERO'),
        (11, 'PASS - 1'),
        (12, 'PASS - 2'),
        (13, 'PASS - 3'),
        (15, 'OVER PASS - IN PLAY'),
        (17, 'ERROR - 0'),
        (18, 'ERROR - FAULT'),
        (19, 'ERROR'),
        (20, 'ZERO'),
  	  	(21, 'SET TO OUTSIDE'),
		    (22, 'SET TO MIDDLE'),
	  	  (23, 'SET TO RIGHTSIDE'),
  		  (24, 'SET TO BACKROW'),
	    	(25, 'SET - DUMP/OVER'),
        (26, 'SET - DUMP/KILL'),
  		  (27, 'ERROR - UNPLAYABLE'),
	    	(28, 'ERROR - FAULT'),
	  	  (29, 'ERROR'),
  		  (30, 'ZERO'),
        (31, 'OVER - IN PLAY'),
        (32, 'FREE BALL'),
        (33, 'KILL'),
        (34, 'FREE BALL KILL'),
        (36, 'ERROR - SHORT'),
        (37, 'ERROR - OUT OF BOUNDS'),
        (38, 'ERROR - FAULT'),
    		(39, 'ERROR'),
        (40, 'ZERO'),
        (41, 'BLOCK - IN PLAY'),
        (42, 'TIP - IN PLAY'),
		    (44, 'STUFF'),
    		(45, 'STUFF - ASSISTED'),
		    (46, 'ERROR - SHORT'),
        (47, 'ERROR - TOOL'),
        (48, 'ERROR - FAULT'),
		    (49, 'ERROR'),
        (60, 'ZERO'),
        (61, 'PASS'),
        (65, 'OVER - IN PLAY'),
        (68, 'MISS'),
		    (69, 'ERROR'),
		    (70, 'ZERO'),
        (77, 'ERROR - CAMPFIRE'),
        (78, 'ERROR - PWNED'),
        (79, 'ERROR');
      
      CREATE TABLE Touch_Qualities (
        quality_id INTEGER PRIMARY KEY,
        quality_description TEXT NOT NULL
      );
      INSERT INTO Touch_Qualities (quality_id, quality_description) VALUES
        (1, 'POOR'),
        (2, 'FAIR'),
        (4, 'GOOD'),
        (5, 'PERFECT'),
        (10, 'WEAK'),
        (15, 'STRONG'),
        (20, 'SAD'),
        (25, 'EPIC');

    - 5. Touch_Seq, Touch_Types, and Touch_Results lookup tables are loaded as dictionaries and enable us to track the sequence of play and record results of play. Note that Touch_Seq for blocks is id 4 and 5 to keep sequence aligned for 1, 2, 3. Two values for block are required to support logging and crediting block assists. Touch_Types id are indexed by 10 to support mapping Touch_Results id to the applicable touch selected (e.g. Touch_Results in range(type_id, type_id+10) are applicaple to Touch_Type with type_id). These tables are static and should only be updated by the app developer.

  - **Live Data Collection ** Data from each possession is appended to a dataframe to track the progress of the match/set. VolleyStat must be able to append the logs collected during the match to the log tables in the database.

      CREATE TABLE Log_Set_Scores (
          match_id INTEGER,
          set_id INTEGER,
          us_score INTEGER,
          them_score INTEGER,
          PRIMARY KEY (match_id,set_id),
          FOREIGN KEY (match_id) REFERENCES Matches(match_id)
      );

    - 6. The Log_Set_Scores table tracks FINAL score of each set by match and set. New entries are generated at the completion of each set. set_id cycles from 1 to 3 or 1 to 5 for each match_id depending on rules set in the Matches table. 

      CREATE TABLE Log_Rally (
          match_id INTEGER NOT NULL,
          set_id INTEGER NOT NULL,
          rally_id INTEGER NOT NULL,
          points_us INTEGER NOT NULL,
          points_them INTEGER NOT NULL,
          rotation INTEGER CHECK(rotation BETWEEN 1 AND 6),
          sanctions TEXT,
          remarks TEXT,
          serve_timestamp TIME,
          PRIMARY KEY (match_id,set_id,rally_id),
          FOREIGN KEY (match_id,set_id) REFERENCES Log_Set_Scores(match_id,set_id)
      );
    - 7. The Log_Rally table tracks the game status at begining of each rally (rally_id) in a match/set. Points_us, points_them, rotation, serve_timestamp, sanctions, and remarks are all tracked as PRIOR TO the rally serve. VolleyStat must be able to append the current rally log to the table on completion of a match. 

      CREATE TABLE IF NOT EXISTS Log_Rotation (
          match_id INTEGER,
          set_id INTEGER,
          rally_id INTEGER,
          rotation INTEGER,
          rotation_slot INTEGER CHECK(rotation_slot BETWEEN 1 AND 6),
          player_id INTEGER,
          PRIMARY KEY (match_id,set_id,rally_id,rotation_slot),
          FOREIGN KEY (player_id) REFERENCES Roster(player_id),
          FOREIGN KEY (match_id,set_id,rally_id) REFERENCES Rally_Log(match_id,set_id,rally_id)
      );
    - 8. The Log_Rotation table tracks the players on the court by their rotation_slot at the begining of each rally (rally_id). This allows us to track who is where on the court during each rally. VolleyStat must be able to append the rotation log to the table on completion of a match.

      CREATE TABLE IF NOT EXISTS Log_Touch (
          match_id INTEGER NOT NULL,
          set_id INTEGER NOT NULL,
          rally_id INTEGER NOT NULL,
          possession_seq INTEGER NOT NULL,
          touch_seq INTEGER NOT NULL CHECK(touch_seq BETWEEN 0 AND 5),
          player_id INTEGER,
          touch_type INTEGER NOT NULL,
          touch_result INTEGER NOT NULL,
          touch_quality INTEGER,
          PRIMARY KEY (match_id,set_id,rally_id,possession_seq, touch_seq),
          FOREIGN KEY (player_id) REFERENCES Roster(player_id),
          FOREIGN KEY (match_id,set_id,rally_id) REFERENCES Log_Rally(match_id,set_id,rally_id),
          FOREIGN KEY (touch_type) REFERENCES Touch_Types(type_id),
          FOREIGN KEY (touch_result) REFERENCES Touch_Results(result_id)
          FOREIGN KEY (touch_quality) REFERENCES Touch_Qualities(quality_id)
      );
    - 9. The Log_Touch is the heart of the data collection effort. This table tracks the player actions on each touch of each possession. The possession_seq begins with 0 for Serve and 1 for Serve-Receive, it then increments by 2 for each possesion in the ralley.  Thus possession_seq doubles as a serve flag, even values when serving and odd values when receiving. If our team scores a point with an odd possession_seq, the side-out actions are taken. Game aware prompts are used to limit input options and guide the data entry. VolleyStat must be able to append the touch log to the table on completion of a match.

  ### State Management
  - Tabular logs of the match:
    set_score_log_df = pd.DataFrame(columns=[
        "match_id", "set_id", "points_us", "points_them"])
    rally_log_df = pd.DataFrame(columns=[
        "match_id", "set_id", "rally_id", "points_us", "points_them",
        "rotation", "sanctions", "remarks", "serve_timestamp"])
    rotation_log_df = pd.DataFrame(columns=[
        "match_id", "set_id", "rally_id", "rotation",
        "rotation_slot", "player_id"])
    touch_log_df = pd.DataFrame(columns=[
        "match_id", "set_id", "rally_id", 
        "possession_seq", "touch_seq", "player_id",
        "touch_type", "touch_result", "touch_quality"])
  - Match state:
    us_team_id
    them_team_id
    match
    match_id 
    set_id
    rally_id
    possession_id
    touch_seq
  - Track where players are
    rotation
    lineup
    liberos
  - Track scores
    points_to_win
    sets_us
    sets_them
    score_us
    score_them
  - Track flags, status, notes
    game_over
    active_set
    subs
    timeouts
    defend
    remarks
    sanctions

  ## Core Architecture
  -- **User Interface**: Using Streamlit for the web interface and organize the app into tabs (mobile/tablet-first layout) that map to the app workflows and provide single-tap access to common actions. 
    Two critical tabs and their responsibilities:
     1. Schedule
       - Create and manage upcoming matches. Add new teams as needed.
       - Quick list of upcoming matches with date, set format, and venue.
       - Ability to select a match and tap "Select Match" to enable Game Tracking with pre-populated with teams/lineup.
     2. Live Game Track 
       - Scoreboard & Controls: big, high-contrast score numbers, large Point Us / Point Them display
       - Input initial set conditions and lineup
       - Graphical display of current rotation with player jersey numbers and names.
       - Primary interface for live data collection during matches.
       - Serve Entry: recognize server (position/jersey) from game state, select serve result (Ace / Error / Return) with one-tap buttons.
       - Opponent Play: simple - Error or Over net to us recording 
       - Rally Entry: Input optional block and up to three touches
       - Enable stopping and logging mid-rally (e.g. injury, whistle)
       - Enable subsitutions during dead ball
       - Minimize typing during play: favor buttons, pickers, and presets; confirm critical actions with lightweight modals only when ambiguous.
    Future tabs:
     3. Stat Viewer
       - Allows selecting a player from a team and viewing event logs, including table of performance by set as well as season totals and averages
     4. Team Management
       - Create/edit teams and seasons.
       - Add, edit, and remove players (name, jersey number, primary position).
       - Roster view with quick keypad for jersey numbers and drag/reorder or compact list for mobile.
  - **Game Logic**: Implement volleyball rules for scoring, rotations, and substitutions. Maintain awareness of game state to provide contextual prompts and automate data entry. 

  ## Key Workflows

  1. Install dependencies:
  ```bash
  pip install -r requirements.txt
  ```

  2. Run the application:
  ```bash
  streamlit run streamlit_app.py
  ```
  ## Integration Points
  - Streamlit for web interface
  - Pandas for data management and statistics
  - SQLite for persistent data storage
  
  ## UI Schematics

  - Theme and touch targets
    - Darkmode-first theme: black or very dark background, white/high-contrast text, pink as the primary accent color for interactive controls.
    - Use large touch targets (44–48px) for primary actions (point buttons, serve/rally results).
    - Compact, high-density controls for lineup and scheduling screens; large, spaced controls for Game Tracking.

  - Layout and navigation
    - Top-level tabs (Scheduling, Game Tracking). Tabs should be visible at the bottom or top depending on platform conventions.
    - In the Game Tracking tab, split UI vertically or with collapsible sections so the most-used controls are immediately visible. Secondary controls (substitutions, settings) should be in a collapsible panel or a slide-over.

  - Game Tracking details (important for developers)
    - Data entry model: each touch is a row in the DataFrame (see Data Model section). 
    - State machine: implement clear rally_step states (0 = serve, 1 = serve-receive, 2+ = in-rally) and a small finite-state machine that drives which UI elements are active.
    - Auto-rotation: when side-out occurs, update rotation automatically and show an animation/brief highlight of the new server.
    - Undo/confirm: allow undo of the last entry; major corrections should open a small editor for that rally row.

  - Accessibility & mobile constraints
    - Use high-contrast text and consider a dyslexia-friendly font option.
    - Support landscape mode for tablets; the Game Tracking tab should scale to a 2-column layout on wider screens (left: controls, right: live log) and collapse to a single column on phones.
    - Minimize keyboard use; prefer pickers and buttons. Provide optional number keypad for quick jersey entry when editing lineups.

  - Visual affordances and feedback
    - Provide subtle haptic or visual feedback on critical taps (point award, rotation change, substitution).
    - Use color-coded badges for event results (green for point-us, red for error, yellow for block).

  Keep the Game Tracking tab focused on minimizing taps during live play and ensuring correctness of recorded events.

