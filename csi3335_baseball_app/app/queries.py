TEAM_IDS_FOR_YEAR = """
SELECT teamID, team_name AS name
FROM teams
WHERE yearID = :yearId
ORDER BY teamID;
"""

TEAM_INFO = """
SELECT
    teamID,
    team_name AS name,
    franchID,
    lgID,
    team_W AS W,
    team_L AS L
FROM teams
WHERE yearID = :yearId
  AND teamID = :teamId
LIMIT 1;
"""

TEAM_BATTING = """
SELECT
    b.playerID,
    CONCAT_WS(' ', NULLIF(p.nameFirst, ''), NULLIF(p.nameLast, '')) AS player_name,
    p.birthYear,
    SUM(b.b_G) AS games,
    SUM(b.b_AB) AS at_bats,
    SUM(b.b_H) AS hits,
    SUM(b.b_2B) AS doubles,
    SUM(b.b_3B) AS triples,
    SUM(b.b_HR) AS home_runs,
    SUM(b.b_RBI) AS runs_batted_in,
    SUM(b.b_BB) AS walks,
    SUM(b.b_SO) AS strikeouts,
    SUM(b.b_SB) AS stolen_bases,
    SUM(b.b_CS) AS caught_stealing,
    SUM(b.b_HBP) AS hit_by_pitch,
    SUM(b.b_SF) AS sacrifice_flies,
    SUM(b.b_SH) AS sacrifice_hits,
    MAX(CASE WHEN hof.inducted = 'Y' THEN 1 ELSE 0 END) AS hall_of_famer,
    MAX(CASE WHEN af.playerID IS NOT NULL THEN 1 ELSE 0 END) AS all_star
FROM batting AS b
INNER JOIN people AS p ON b.playerID = p.playerID
LEFT JOIN halloffame AS hof
       ON hof.playerID = b.playerID
      AND hof.inducted = 'Y'
LEFT JOIN allstarfull AS af
       ON af.playerID = b.playerID
      AND af.yearID = b.yearId
WHERE b.yearId = :yearId
  AND b.teamID = :teamId
GROUP BY b.playerID, p.nameFirst, p.nameLast, p.birthYear
ORDER BY home_runs DESC, hits DESC;
"""

LEAGUE_BATTING_AGGREGATES = """
SELECT
    SUM(b.b_G) AS games,
    SUM(b.b_AB) AS at_bats,
    SUM(b.b_H) AS hits,
    SUM(b.b_2B) AS doubles,
    SUM(b.b_3B) AS triples,
    SUM(b.b_HR) AS home_runs,
    SUM(b.b_BB) AS walks,
    SUM(b.b_SO) AS strikeouts,
    SUM(b.b_SB) AS stolen_bases,
    SUM(b.b_CS) AS caught_stealing,
    SUM(b.b_HBP) AS hit_by_pitch,
    SUM(b.b_SF) AS sacrifice_flies,
    SUM(b.b_SH) AS sacrifice_hits
FROM batting AS b
WHERE b.yearId = :yearId;
"""
