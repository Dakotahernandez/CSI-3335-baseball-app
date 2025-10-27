TEAM_IDS_FOR_YEAR = """
SELECT teamID, name
FROM teams
WHERE yearID = :yearId
ORDER BY teamID;
"""

TEAM_INFO = """
SELECT teamID, name, franchID, lgID, W, L
FROM teams
WHERE yearID = :yearId
  AND teamID = :teamId
LIMIT 1;
"""

TEAM_BATTING = """
SELECT
    CONCAT_WS(' ', NULLIF(p.nameFirst, ''), NULLIF(p.nameLast, '')) AS player_name,
    b.AB AS at_bats,
    b.H AS hits,
    b.HR AS home_runs,
    b.RBI AS runs_batted_in,
    b.BB AS walks,
    b.SO AS strikeouts
FROM batting AS b
INNER JOIN people AS p ON b.playerID = p.playerID
WHERE b.yearID = :yearId
  AND b.teamID = :teamId
ORDER BY b.HR DESC, b.H DESC;
"""
