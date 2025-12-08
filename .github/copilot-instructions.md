# AI Agent Instructions for VB_scorekeeper

  ## Project Overview
  This is a web application for collecting volleyball player statistics in real-time.
  To support this, it must minimize user input requirements while maximizing data accuracy and completeness. The app must be game aware, understanding volleyball rules and player rotations to support prompting the user for necessary inputs only. The game log files must be structured and exportable to support post-game analysis. The app will be run on tablets or phones during games and screen layout must be optimized for quick access, minimal navigation, and intuitive game flow. For now, team management and statistical analysis functions will be handled in a separate application. This application focuses on collecting player statistics at the touch level.

  ## Data Model
  - **Persistent Records** are stored in tables in a sqlite database "OB_VBC.db" with schema:
    - 1. The teams table is used to store both our team and opponent teams. This table enables mapping human readable (team_name and team_abbv) team names to team_id, as well as storing additional team metadata. Adding new teams throughout the season is important as club games are often tournament vs league play. 
      CREATE TABLE Teams (
          team_id INTEGER PRIMARY KEY AUTOINCREMENT,
          team_name TEXT NOT NULL,
          team_abbv TEXT NOT NULL,
          club TEXT,
          season TEXT,
          team_hometown TEXT,
          team_coach TEXT
      );

    - 2. The Rosters table is used to store players we are collecting performance stats on. This table enables mapping human readable labels (player_name, player_jersey) to player_id for players on our teams. Players are assigned to our teams using player_team; tracking players on opponent teams is neither required nor desired. Player position may be used in some prompts, but coaches may change player assignments from set to set, so it is NOT constraining. The Player_Roster will generally be static throughout the season, with few changes. Any need to update/modify can be handeled in a separate management application for now. 
      CREATE TABLE Rosters (
          player_id INTEGER PRIMARY KEY AUTOINCREMENT,
          player_name TEXT NOT NULL,
          player_jersey INTEGER NOT NULL CHECK(player_jersey BETWEEN 0 AND 99),
          player_position INTEGER,
          player_team INTEGER NOT NULL,
          FOREIGN KEY (player_team) REFERENCES Teams(team_id), 
          FOREIGN KEY (player_position) REFERENCES Player_Positions(position_id), 
          UNIQUE(player_team, player_jersey)
      )

    - 3. The Matches table stores the schedule for our teams. This table enables tracking each match and the associated match rules. Adding new matches is important throughout the season. An entry in the Matches table is required prior to data collection. 
      CREATE TABLE Matches (
          match_id INTEGER PRIMARY KEY AUTOINCREMENT,
          match_date DATE,
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

    Match_Types, Match_Rules, and Match_Criteria lookup tables are loaded as dictionaries and enable us to set the type, rules, and victory criteria for each match. These tables are static and should only be updated by the app developer.

      CREATE TABLE Match_Types(
	        type_id INTEGER PRIMARY KEY,
	        match_type TEXT UNIQUE NOT NULL
      );
      INSERT INTO Match_Types (type_id, match_type) VALUES
        (1,	'League'),
        (2,	'Tournament'),
        (3,	'Scrimage');

      CREATE TABLE Match_Rules (
          rule_id INTEGER PRIMARY KEY,
          rule_description TEXT UNIQUE NOT NULL
      );
      INSERT INTO Match_Rules (rule_id, rule_description) VALUES
        (1, 'Court: 6 on 6'),
        (2, 'Beach: 2 on 2'),
        (3, 'Grass: 3 on 3'),
        (4, 'Pickup: 4 on 4');

      CREATE TABLE Match_Criteria(
          criteria_id INTEGER PRIMARY KEY,
          criteria_description TEXT UNIQUE NOT NULL
      );
      INSERT INTO Match_Criteria (criteria_id, criteria_description) VALUES
        (1, 'Best of 3'),
        (2, '3 Sets'),
        (3, 'Best of 5'),
        (4, 'Single Set'),

    - 4. The Log_Set_Scores table tracks final score of each set by match and set. New entries are generated at the completion of each set. set_id cycles from 1 to 3 or 1 to 5 for each match_id depending on rules set in the Matches table
      CREATE TABLE Log_Set_Scores (
          match_id INTEGER,
          set_id INTEGER,
          us_score INTEGER,
          them_score INTEGER,
          PRIMARY KEY (match_id,set_id),
          FOREIGN KEY (match_id) REFERENCES Matches(match_id)
      );

    - 5. The Log_Rally table tracks the game status at begining of each rally (rally_id) in a match/set. Points_us, points_them, rotation, serve_timestamp, sanctions, and remarks are all tracked as prior to the rally serve. 
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

    - 6. The Log_Rotation table tracks the players on the court by their rotation_slot at the begining of each rally (rally_id). 
      CREATE TABLE IF NOT EXISTS Log_Rotation (
          match_id INTEGER,
          set_id INTEGER,
          rally_id INTEGER,
          rotation_slot INTEGER CHECK(rotation_slot BETWEEN 1 AND 6),
          player_id INTEGER,
          PRIMARY KEY (match_id,set_id,rally_id,rotation_slot),
          FOREIGN KEY (player_id) REFERENCES Player_Roster(player_id),
          FOREIGN KEY (match_id,set_id,rally_id) REFERENCES Rally_Log(match_id,set_id,rally_id)
      );

    - 7. The Log_Touch is the heart of the data collection effort. This table tracks the player actions on each touch of each possession. The possession_seq begins with 0 for Serve and 1 for Serve-Receive, it then increments by 2 for each possesion in the ralley.  Thus possession_seq doubles as a serve flag, even values when serving and odd values when receiving. If our team scores a point with an odd possession_seq, the side-out actions are taken. Game aware prompts are used to limit input options and guide the data entry. 

      CREATE TABLE Log_Touch (
          match_id INTEGER NOT NULL,
          set_id INTEGER NOT NULL,
          rally_id INTEGER NOT NULL,
          possession_seq INTEGER NOT NULL,
          touch_seq INTEGER NOT NULL CHECK(touch_seq BETWEEN 0 AND 5),
          touch_id INTEGER,
          touch_type INTEGER NOT NULL,
          touch_result INTEGER NOT NULL,
          touch_quality INTEGER,
          PRIMARY KEY (match_id,set_id,rally_id,possession_seq, touch_seq),
          FOREIGN KEY (touch_id) REFERENCES Rosters(player_id),
          FOREIGN KEY (match_id,set_id,rally_id) REFERENCES Log_Rally(match_id,set_id,rally_id),
          FOREIGN KEY (touch_type) REFERENCES Touch_Types(type_id),
          FOREIGN KEY (touch_result) REFERENCES Touch_Results(result_id)
          FOREIGN KEY (touch_quality) REFERENCES Touch_Qualities(quality_id)
      );

    The touch_seq is {0: SERVE, 1: ONE, 2: TWO, 3: THREE, 4: BLOCK, 5: BLOCK}. Two values for block are required to support logging and crediting a block with assist. touch_type, touch_result, and touch_quality lookup tables areloaded as dictionaries and enable us to track and score each touch. These tables are static and should only be updated by the app developer.

      CREATE TABLE Touch_Types (
        type_id INTEGER PRIMARY KEY,
        touch_type TEXT UNIQUE NOT NULL
      );
      INSERT INTO Touch_Types (type_id, touch_type) VALUES
        (1, 'SERVE'),
        (2, 'BLOCK'),
        (3, 'DIG'),
        (4, 'PASS'),
        (5, 'SET'),
        (6, 'ATTACK'),
        (7, 'TEAM_ERROR');
      
      CREATE TABLE Touch_Results (
        result_id INTEGER PRIMARY KEY,
        touch_result TEXT UNIQUE NOT NULL
      );
      INSERT INTO Touch_Results (result_id, touch_result) VALUES
        (1, 'TOUCH'),
        (2, 'ZERO'),
        (3, 'ERROR'),
        (4, 'ASSIST'),
        (5, 'ACE'),
        (6, 'KILL'),
        (7, 'STUFF');
      
      CREATE TABLE Touch_Qualities (
        quality_id INTEGER PRIMARY KEY,
        quality_description TEXT NOT NULL,
      );
      INSERT INTO Touch_Qualities (quality_id, quality_description) VALUES
        (0, 'ERROR'),
        (1, 'FAIR'),
        (2, 'GOOD'),
        (3, 'PERFECT'),
        (5, 'WEAK'),
        (7, 'STRONG'),
        (8, 'TOOL'),
        (9, 'FAULT')
        (10, 'WEAK:NotReturned')
        (14, 'STRONG:NotReturned');

  - **Live Data Collection ** Data from each possession is appended to a dataframe to track the progress of the match/set. 

  ## Core Architecture
  -- **User Interface**: Using Streamlit for the web interface and organize the app into tabs (mobile/tablet-first layout) that map to the app workflows and provide single-tap access to common actions. 
    Two critical tabs and their responsibilities:
     1. Match Schedules
       - Create and manage upcoming matches.
       - Quick list of upcoming matches with date, set format, and venue.
       - Ability to select a match and tap "Start Match" to open the Game Tracking tab pre-populated with teams/lineup.
     2. Rally Tracking 
       - Split into compact sub-sections for quick access: Scoreboard & Controls, Serve Entry, Rally Entry, Rotation/Subs, Live Event Log.
       - Scoreboard & Controls: big, high-contrast score numbers, large Point Us / Point Them buttons, current rotation indicator, and a single "Next Rally" action.
       - Serve Entry: recognize server (position/jersey) from game state, select serve result (Ace / Error / Return) with one-tap buttons.
       - Rally Entry: streamlined 1-2-3 touch input with quick pickers for player and result; block handling with quick blocker selection and block result options.
       - Rotation & Substitutions: compact rotational diagram and one-tap substitutions; auto-apply rotation on side-out when appropriate.
       - Live Event Log: append each rally as a structured row; allow quick undo and edit of last event.
       - Minimize typing during play: favor buttons, pickers, and presets; confirm critical actions with lightweight modals only when ambiguous.
    Future tabs:
     3. Stat Viewer
       - Allows selecting a player from a team and viewing event logs, including table of performance by set as well as season totals and averages
     4. Team Management
       - Create/edit teams and seasons.
       - Add, edit, and remove players (name, jersey number, primary position).
       - Roster view with quick keypad for jersey numbers and drag/reorder or compact list for mobile.
  - **Game Logic**: Implement volleyball rules for scoring, rotations, and substitutions. Maintain awareness of game state to provide contextual prompts and automate data entry. See `/.archive/streamlit_app.py` for reference logic design.


  ## Key Workflows

  ### Development Setup
  1. Install dependencies:
  ```bash
  pip install -r requirements.txt
  ```

  2. Run the application:
  ```bash
  streamlit run streamlit_app.py
  ```

  ### State Management
  - Key state variables:
    - 'match_id', 'set_id': Current match set
    - 'rally_id', `score_us`, `score_them`: Current set rally and set scores
    - `rotation`: Current player rotation (1-6)
    - `possession_seq`: Tracks serve/return and step sequence in rally

  ### Data Structure Patterns
  - Each game event is stored as a row in the DataFrame with:
    - Player positions and jersey numbers
    - Touch sequences (serve, block, 3 touches)
    - Sanctions
  - Example DataFrame schema:
  ```python
  {
      "position_1": int,  # Jersey numbers for each position
      "position_2": int,
      ...
      "rotation": int,
      "touch_serve": Optional[str],
      "touch_block": Optional[str],
      "touch_block_asst": Optional[str],
      "touch_1": Optional[str],
      "touch_2": Optional[str],
      "touch_3": Optional[str],
      "sanctions": Optional[str]
  }
  ```

  ## Common Operations
  - Use `reset_rally_results()` to clear per-rally state
  - Call `add_new_row()` to record a new game event
  - Point scoring functions (`point_us()`, `point_them()`) handle rotation changes automatically

  ## UI Schematics

  - Theme and touch targets
    - Darkmode-first theme: black or very dark background, white/high-contrast text, pink as the primary accent color for interactive controls.
    - Use large touch targets (minimum 44–48px) for primary actions (point buttons, serve/rally results).
    - Compact, high-density controls for lineup and scheduling screens; large, spaced controls for Game Tracking.

  - Layout and navigation
    - Four top-level tabs (Team Management, Scheduling, Game Tracking, Archive). Tabs should be visible at the bottom or top depending on platform conventions; keep them always one-tap away.
    - In the Game Tracking tab, split UI vertically or with collapsible sections so the most-used controls are immediately visible (Scoreboard + Quick Serve + Rally). Secondary controls (substitutions, settings) should be in a collapsible panel or a slide-over.

  - Game Tracking details (important for developers)
    - Data entry model: each rally is a row in the DataFrame (see Data Model section). Rows must include lineup snapshot, rotation, touch sequence (serve, block, touch1-3), and sanctions.
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

  ## Integration Points
  - Streamlit for web interface
  - Pandas for data management and statistics