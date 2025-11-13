from decimal import Decimal

import pandas as pd
import numpy as np
from flask import Blueprint, flash, make_response, redirect, render_template, request, url_for
from sqlalchemy import text

from . import db
from .forms import TeamYearForm, PlayerCompareForm
from . import queries

core_bp = Blueprint('core', __name__)


def _team_choices_for_year(year: int):
    if not year:
        return []
    with db.engine.connect() as connection:
        result = connection.execute(text(queries.TEAM_IDS_FOR_YEAR), {'yearId': year})
        rows = result.mappings().all()
    return [(row['teamID'], f"{row['teamID']} — {row['name']}") for row in rows]


def _team_metadata(team_id: str, year_id: int):
    with db.engine.connect() as connection:
        result = connection.execute(text(queries.TEAM_INFO), {'teamId': team_id, 'yearId': year_id})
        record = result.mappings().first()
    return dict(record) if record else None


def _league_batting_summary(year_id: int):
    with db.engine.connect() as connection:
        result = connection.execute(text(queries.LEAGUE_BATTING_AGGREGATES), {'yearId': year_id})
        record = result.mappings().first()
    if not record:
        return {}
    cleaned = {}
    for key, value in dict(record).items():
        if value is None:
            cleaned[key] = 0
        elif isinstance(value, Decimal):
            cleaned[key] = float(value)
        else:
            cleaned[key] = value
    return cleaned


def _team_batting(team_id: str, year_id: int):
    with db.engine.connect() as connection:
        dataframe = pd.read_sql_query(
            text(queries.TEAM_BATTING),
            connection,
            params={'teamId': team_id, 'yearId': year_id},
        )
    if dataframe.empty:
        return dataframe, {}, pd.DataFrame()

    numeric_columns = [col for col in dataframe.columns if col not in {'playerID', 'player_name', 'birthYear'}]
    dataframe[numeric_columns] = dataframe[numeric_columns].fillna(0)

    age_series = np.where(
        dataframe['birthYear'].notna() & (dataframe['birthYear'] > 0),
        year_id - dataframe['birthYear'],
        np.nan,
    )
    dataframe['age'] = age_series

    singles = (dataframe['hits'] - dataframe['doubles'] - dataframe['triples'] - dataframe['home_runs']).clip(lower=0)
    total_bases = singles + (2 * dataframe['doubles']) + (3 * dataframe['triples']) + (4 * dataframe['home_runs'])
    plate_appearances = (
        dataframe['at_bats']
        + dataframe['walks']
        + dataframe['hit_by_pitch']
        + dataframe['sacrifice_flies']
        + dataframe['sacrifice_hits']
    )

    dataframe['avg'] = np.where(dataframe['at_bats'] > 0, dataframe['hits'] / dataframe['at_bats'], 0)
    dataframe['obp'] = np.where(
        plate_appearances > 0,
        (dataframe['hits'] + dataframe['walks'] + dataframe['hit_by_pitch']) / plate_appearances,
        0,
    )
    dataframe['slg'] = np.where(dataframe['at_bats'] > 0, total_bases / dataframe['at_bats'], 0)
    dataframe['ops'] = dataframe['obp'] + dataframe['slg']
    dataframe['iso'] = dataframe['slg'] - dataframe['avg']

    babip_denom = (
        dataframe['at_bats']
        - dataframe['strikeouts']
        - dataframe['home_runs']
        + dataframe['sacrifice_flies']
    )
    dataframe['babip'] = np.where(babip_denom > 0, (dataframe['hits'] - dataframe['home_runs']) / babip_denom, 0)

    sb_attempts = dataframe['stolen_bases'] + dataframe['caught_stealing']
    dataframe['sb_pct'] = np.where(sb_attempts > 0, dataframe['stolen_bases'] / sb_attempts, np.nan)

    singles_weight = 0.89
    doubles_weight = 1.27
    triples_weight = 1.62
    home_run_weight = 2.1
    walk_weight = 0.69
    hbp_weight = 0.72

    woba_numerator = (
        walk_weight * dataframe['walks']
        + hbp_weight * dataframe['hit_by_pitch']
        + singles_weight * singles
        + doubles_weight * dataframe['doubles']
        + triples_weight * dataframe['triples']
        + home_run_weight * dataframe['home_runs']
    )
    woba_denominator = (
        dataframe['at_bats']
        + dataframe['walks']
        + dataframe['hit_by_pitch']
        + dataframe['sacrifice_flies']
    )
    dataframe['woba'] = np.where(woba_denominator > 0, woba_numerator / woba_denominator, 0)

    league_summary = _league_batting_summary(year_id)
    league_ops = None
    if league_summary:
        league_singles = (
            league_summary['hits']
            - league_summary['doubles']
            - league_summary['triples']
            - league_summary['home_runs']
        )
        league_total_bases = (
            league_singles
            + 2 * league_summary['doubles']
            + 3 * league_summary['triples']
            + 4 * league_summary['home_runs']
        )
        league_plate_appearances = (
            league_summary['at_bats']
            + league_summary['walks']
            + league_summary['hit_by_pitch']
            + league_summary['sacrifice_flies']
        )
        league_avg = (
            league_summary['hits'] / league_summary['at_bats'] if league_summary['at_bats'] else 0
        )
        league_obp = (
            (league_summary['hits'] + league_summary['walks'] + league_summary['hit_by_pitch']) / league_plate_appearances
            if league_plate_appearances
            else 0
        )
        league_slg = league_total_bases / league_summary['at_bats'] if league_summary['at_bats'] else 0
        league_avg = float(league_avg)
        league_obp = float(league_obp)
        league_slg = float(league_slg)
        league_ops = float(league_obp + league_slg) if (league_obp or league_slg) else 0.0
    else:
        league_avg = league_obp = league_slg = 0

    dataframe['ops_plus'] = np.where(
        league_ops and league_ops > 0,
        np.where(dataframe['ops'] > 0, (dataframe['ops'] / league_ops) * 100, np.nan),
        np.nan,
    )

    def _badge_variants(row):
        html_badges = []
        text_badges = []
        if row['hall_of_famer']:
            html_badges.append('<span class="badge badge-hof">Hall of Fame</span>')
            text_badges.append('Hall of Fame')
        if row['all_star']:
            badge_text = f"All-Star {year_id}"
            html_badges.append(f'<span class="badge badge-allstar">{badge_text}</span>')
            text_badges.append(badge_text)
        return pd.Series({
            'badges_html': ' '.join(html_badges),
            'badges_text': ', '.join(text_badges),
        })

    badge_variants = dataframe.apply(_badge_variants, axis=1)
    dataframe = pd.concat([dataframe, badge_variants], axis=1)

    comparison_columns = [
        'playerID',
        'player_name',
        'age',
        'games',
        'at_bats',
        'hits',
        'doubles',
        'triples',
        'home_runs',
        'runs_batted_in',
        'walks',
        'strikeouts',
        'stolen_bases',
        'caught_stealing',
        'sb_pct',
        'avg',
        'obp',
        'slg',
        'ops',
        'iso',
        'babip',
        'woba',
        'ops_plus',
        'hall_of_famer',
        'all_star',
        'badges_text',
        'badges_html',
    ]
    comparison_df = dataframe[comparison_columns].copy()

    def _format_rate(value: float) -> str:
        return f"{value:.3f}"

    def _format_percent(value: float) -> str:
        return f"{value * 100:.1f}%" if not np.isnan(value) else "—"

    display_columns = pd.DataFrame({
        'Player': dataframe['player_name'],
        'Badges': dataframe['badges_html'],
        'Age': dataframe['age'].apply(lambda v: int(v) if not np.isnan(v) else '—'),
        'Games': dataframe['games'].astype(int),
        'At Bats': dataframe['at_bats'].astype(int),
        'Hits': dataframe['hits'].astype(int),
        'Doubles': dataframe['doubles'].astype(int),
        'Triples': dataframe['triples'].astype(int),
        'Home Runs': dataframe['home_runs'].astype(int),
        'RBIs': dataframe['runs_batted_in'].astype(int),
        'Walks': dataframe['walks'].astype(int),
        'Strikeouts': dataframe['strikeouts'].astype(int),
        'Stolen Bases': dataframe['stolen_bases'].astype(int),
        'Caught Stealing': dataframe['caught_stealing'].astype(int),
        'SB%': dataframe['sb_pct'].apply(_format_percent),
        'AVG': dataframe['avg'].apply(_format_rate),
        'OBP': dataframe['obp'].apply(_format_rate),
        'SLG': dataframe['slg'].apply(_format_rate),
        'OPS': dataframe['ops'].apply(_format_rate),
        'ISO': dataframe['iso'].apply(_format_rate),
        'BABIP': dataframe['babip'].apply(_format_rate),
        'wOBA': dataframe['woba'].apply(_format_rate),
        'OPS+': dataframe['ops_plus'].apply(lambda v: f"{int(round(v))}" if not np.isnan(v) else '—'),
    })

    team_at_bats = dataframe['at_bats'].sum()
    team_hits = dataframe['hits'].sum()
    team_walks = dataframe['walks'].sum()
    team_hbp = dataframe['hit_by_pitch'].sum()
    team_total_bases = total_bases.sum()
    team_plate_appearances = plate_appearances.sum()
    team_avg_val = team_hits / team_at_bats if team_at_bats else 0
    team_obp_val = (team_hits + team_walks + team_hbp) / team_plate_appearances if team_plate_appearances else 0
    team_slg_val = team_total_bases / team_at_bats if team_at_bats else 0
    team_ops_val = team_obp_val + team_slg_val
    team_iso_val = team_slg_val - team_avg_val
    team_babip_denom = babip_denom.sum()
    team_babip_val = (team_hits - dataframe['home_runs'].sum()) / team_babip_denom if team_babip_denom else 0
    team_sb_attempts = (dataframe['stolen_bases'] + dataframe['caught_stealing']).sum()
    team_sb_pct = (dataframe['stolen_bases'].sum() / team_sb_attempts) if team_sb_attempts else np.nan
    team_woba_denom = team_plate_appearances
    team_woba_val = (
        (
            walk_weight * team_walks
            + hbp_weight * dataframe['hit_by_pitch'].sum()
            + singles_weight * singles.sum()
            + doubles_weight * dataframe['doubles'].sum()
            + triples_weight * dataframe['triples'].sum()
            + home_run_weight * dataframe['home_runs'].sum()
        ) / team_woba_denom
        if team_woba_denom
        else 0
    )

    team_ops_plus_val = ((team_ops_val / league_ops) * 100) if league_ops and league_ops > 0 else np.nan

    totals_row = {
        'Player': 'Team Totals',
        'Badges': '',
        'Age': '',
        'Games': int(dataframe['games'].sum()),
        'At Bats': int(dataframe['at_bats'].sum()),
        'Hits': int(dataframe['hits'].sum()),
        'Doubles': int(dataframe['doubles'].sum()),
        'Triples': int(dataframe['triples'].sum()),
        'Home Runs': int(dataframe['home_runs'].sum()),
        'RBIs': int(dataframe['runs_batted_in'].sum()),
        'Walks': int(dataframe['walks'].sum()),
        'Strikeouts': int(dataframe['strikeouts'].sum()),
        'Stolen Bases': int(dataframe['stolen_bases'].sum()),
        'Caught Stealing': int(dataframe['caught_stealing'].sum()),
        'SB%': _format_percent(team_sb_pct),
        'AVG': _format_rate(team_avg_val),
        'OBP': _format_rate(team_obp_val),
        'SLG': _format_rate(team_slg_val),
        'OPS': _format_rate(team_ops_val),
        'ISO': _format_rate(team_iso_val),
        'BABIP': _format_rate(team_babip_val),
        'wOBA': _format_rate(team_woba_val),
        'OPS+': f"{int(round(team_ops_plus_val))}" if not np.isnan(team_ops_plus_val) else '—',
    }
    display_columns = pd.concat([display_columns, pd.DataFrame([totals_row])], ignore_index=True)

    def _leader(series: pd.Series) -> str:
        filtered = series.dropna()
        if filtered.empty:
            return 'N/A'
        idx = filtered.idxmax()
        return dataframe.loc[idx, 'player_name']

    leaders = {}
    if not dataframe.empty:
        leaders = {
            'home_run_leader': _leader(dataframe['home_runs']),
            'avg_leader': _leader(dataframe['avg']),
            'ops_leader': _leader(dataframe['ops']),
            'woba_leader': _leader(dataframe['woba']),
            'sb_leader': _leader(dataframe['stolen_bases']),
        }

    summary = {
        'team_avg': totals_row['AVG'],
        'team_obp': totals_row['OBP'],
        'team_slg': totals_row['SLG'],
        'team_ops': totals_row['OPS'],
        'team_iso': totals_row['ISO'],
        'team_babip': totals_row['BABIP'],
        'team_woba': totals_row['wOBA'],
        'team_sb_pct': totals_row['SB%'],
        'home_runs': int(dataframe['home_runs'].sum()),
        'stolen_bases': int(dataframe['stolen_bases'].sum()),
        'hall_of_famers': int(dataframe['hall_of_famer'].sum()),
        'all_stars': int(dataframe['all_star'].sum()),
        'leaders': leaders,
        'league_avg': _format_rate(league_avg),
        'league_obp': _format_rate(league_obp),
        'league_slg': _format_rate(league_slg),
        'league_ops': _format_rate(league_ops) if league_ops is not None else '0.000',
        'team_ops_plus': f"{int(round(team_ops_plus_val))}" if not np.isnan(team_ops_plus_val) else '—',
    }

    return display_columns, summary, comparison_df


@core_bp.route('/', methods=['GET', 'POST'])
def index():
    form = TeamYearForm()
    has_choices = False

    year_value = form.year.data if request.method == 'POST' else request.args.get('year', type=int)
    if request.method == 'GET' and year_value:
        form.year.data = year_value

    choices = _team_choices_for_year(year_value) if year_value else []
    if choices:
        form.team_id.choices = choices
        has_choices = True
        valid_ids = {choice[0] for choice in choices}
        if not form.team_id.data or form.team_id.data not in valid_ids:
            form.team_id.data = choices[0][0]
    else:
        form.team_id.choices = []

    if request.method == 'POST':
        if form.submit_load.data:
            if not has_choices:
                flash('No teams found for that season. Enter a year between 1871 and 2024.', 'warning')
            return render_template('index.html', form=form, has_choices=has_choices)

        if form.submit_view.data:
            form_valid = form.validate_on_submit()
            if not has_choices:
                flash('Load teams for the selected season before viewing stats.', 'warning')
            if form_valid and has_choices:
                return redirect(url_for('core.team_view', team_id=form.team_id.data, year_id=form.year.data))

    return render_template('index.html', form=form, has_choices=has_choices)


@core_bp.route('/team/<team_id>/<int:year_id>')
def team_view(team_id: str, year_id: int):
    if year_id < 1871 or year_id > 2024:
        message = f"Season {year_id} is outside the supported range."
        return render_template('error.html', message=message), 404

    team = _team_metadata(team_id, year_id)
    if not team:
        message = f"No records for team {team_id} in {year_id}."
        return render_template('error.html', message=message), 404

    batting_df, extra_summary, _ = _team_batting(team_id, year_id)
    if batting_df.empty:
        message = f"No batting stats available for team {team_id} in {year_id}."
        return render_template('error.html', message=message), 404

    table_html = batting_df.to_html(classes='data-table', index=False, border=0, justify='center', escape=False)
    leaders = extra_summary.get('leaders', {}) if extra_summary else {}

    return render_template(
        'team.html',
        team=team,
        year_id=year_id,
        table_html=table_html,
        summary=extra_summary,
        leaders=leaders,
    )

@core_bp.route('/team/<team_id>/<int:year_id>/download')
def team_download(team_id: str, year_id: int):
    if year_id < 1871 or year_id > 2024:
        message = f"Season {year_id} is outside the supported range."
        return render_template('error.html', message=message), 404

    team = _team_metadata(team_id, year_id)
    if not team:
        message = f"No records for team {team_id} in {year_id}."
        return render_template('error.html', message=message), 404

    display_df, summary, raw_df = _team_batting(team_id, year_id)
    if display_df.empty:
        message = f"No batting stats available for team {team_id} in {year_id}."
        return render_template('error.html', message=message), 404

    if raw_df.empty:
        message = f"No batting stats available for team {team_id} in {year_id}."
        return render_template('error.html', message=message), 404

    def _format_rate(value: float) -> str:
        return f"{value:.3f}" if not np.isnan(value) else '—'

    def _format_percent(value: float) -> str:
        return f"{value * 100:.1f}%" if not np.isnan(value) else '—'

    def _format_int(value) -> str:
        if value is None or (isinstance(value, float) and np.isnan(value)):
            return ''
        return str(int(value))

    export_df = pd.DataFrame({
        'Player ID': raw_df['playerID'],
        'Player': raw_df['player_name'],
        'Age': raw_df['age'].apply(lambda v: _format_int(v) if not np.isnan(v) else ''),
        'Games': raw_df['games'].astype(int),
        'At Bats': raw_df['at_bats'].astype(int),
        'Hits': raw_df['hits'].astype(int),
        'Doubles': raw_df['doubles'].astype(int),
        'Triples': raw_df['triples'].astype(int),
        'Home Runs': raw_df['home_runs'].astype(int),
        'RBIs': raw_df['runs_batted_in'].astype(int),
        'Walks': raw_df['walks'].astype(int),
        'Strikeouts': raw_df['strikeouts'].astype(int),
        'Stolen Bases': raw_df['stolen_bases'].astype(int),
        'Caught Stealing': raw_df['caught_stealing'].astype(int),
        'SB%': raw_df['sb_pct'].apply(_format_percent),
        'AVG': raw_df['avg'].apply(_format_rate),
        'OBP': raw_df['obp'].apply(_format_rate),
        'SLG': raw_df['slg'].apply(_format_rate),
        'OPS': raw_df['ops'].apply(_format_rate),
        'ISO': raw_df['iso'].apply(_format_rate),
        'BABIP': raw_df['babip'].apply(_format_rate),
        'wOBA': raw_df['woba'].apply(_format_rate),
        'OPS+': raw_df['ops_plus'].apply(lambda v: _format_int(v) if not np.isnan(v) else '—'),
        'Hall of Fame': raw_df['hall_of_famer'].apply(lambda v: 'Yes' if v else 'No'),
        'All-Star': raw_df['all_star'].apply(lambda v: 'Yes' if v else 'No'),
        'Badges': raw_df['badges_text'],
    })

    totals_row = {
        'Player ID': '',
        'Player': 'Team Totals',
        'Age': '',
        'Games': str(int(raw_df['games'].sum())),
        'At Bats': str(int(raw_df['at_bats'].sum())),
        'Hits': str(int(raw_df['hits'].sum())),
        'Doubles': str(int(raw_df['doubles'].sum())),
        'Triples': str(int(raw_df['triples'].sum())),
        'Home Runs': str(int(raw_df['home_runs'].sum())),
        'RBIs': str(int(raw_df['runs_batted_in'].sum())),
        'Walks': str(int(raw_df['walks'].sum())),
        'Strikeouts': str(int(raw_df['strikeouts'].sum())),
        'Stolen Bases': str(int(raw_df['stolen_bases'].sum())),
        'Caught Stealing': str(int(raw_df['caught_stealing'].sum())),
        'SB%': summary.get('team_sb_pct', ''),
        'AVG': summary.get('team_avg', ''),
        'OBP': summary.get('team_obp', ''),
        'SLG': summary.get('team_slg', ''),
        'OPS': summary.get('team_ops', ''),
        'ISO': summary.get('team_iso', ''),
        'BABIP': summary.get('team_babip', ''),
        'wOBA': summary.get('team_woba', ''),
        'OPS+': summary.get('team_ops_plus', ''),
        'Hall of Fame': '',
        'All-Star': '',
        'Badges': '',
    }
    export_df = pd.concat([export_df, pd.DataFrame([totals_row])], ignore_index=True)
    csv_data = export_df.to_csv(index=False)
    filename = f"{team_id}_{year_id}_batting.csv"
    response = make_response(csv_data)
    response.headers['Content-Type'] = 'text/csv'
    response.headers['Content-Disposition'] = f'attachment; filename={filename}'
    return response


@core_bp.route('/team/<team_id>/<int:year_id>/compare', methods=['GET', 'POST'])
def team_compare(team_id: str, year_id: int):
    if year_id < 1871 or year_id > 2024:
        message = f"Season {year_id} is outside the supported range."
        return render_template('error.html', message=message), 404

    team = _team_metadata(team_id, year_id)
    if not team:
        message = f"No records for team {team_id} in {year_id}."
        return render_template('error.html', message=message), 404

    _, summary, player_df = _team_batting(team_id, year_id)
    if player_df.empty:
        message = f"No batting stats available for team {team_id} in {year_id}."
        return render_template('error.html', message=message), 404

    player_df = player_df.copy()
    player_df['playerID'] = player_df['playerID'].astype(str)
    player_df = player_df.sort_values('player_name').reset_index(drop=True)

    players_lookup = player_df.set_index('playerID', drop=False)
    choices = [(row['playerID'], row['player_name']) for _, row in player_df.iterrows()]

    form = PlayerCompareForm()
    form.player_one.choices = choices
    form.player_two.choices = choices

    preselected_one = request.args.get('player_one', type=str)
    preselected_two = request.args.get('player_two', type=str)
    if request.method == 'GET':
        if preselected_one and preselected_one in players_lookup.index:
            form.player_one.data = preselected_one
        if preselected_two and preselected_two in players_lookup.index:
            form.player_two.data = preselected_two

    stat_config = [
        ('age', 'Age', 'int'),
        ('games', 'Games', 'int'),
        ('at_bats', 'At Bats', 'int'),
        ('hits', 'Hits', 'int'),
        ('doubles', 'Doubles', 'int'),
        ('triples', 'Triples', 'int'),
        ('home_runs', 'Home Runs', 'int'),
        ('runs_batted_in', 'RBIs', 'int'),
        ('walks', 'Walks', 'int'),
        ('strikeouts', 'Strikeouts', 'int'),
        ('stolen_bases', 'Stolen Bases', 'int'),
        ('caught_stealing', 'Caught Stealing', 'int'),
        ('sb_pct', 'SB%', 'percent'),
        ('avg', 'AVG', 'rate'),
        ('obp', 'OBP', 'rate'),
        ('slg', 'SLG', 'rate'),
        ('ops', 'OPS', 'rate'),
        ('iso', 'ISO', 'rate'),
        ('babip', 'BABIP', 'rate'),
        ('woba', 'wOBA', 'rate'),
        ('ops_plus', 'OPS+', 'ops_plus'),
    ]

    def _format_stat(value, metric_type: str) -> str:
        if pd.isna(value):
            return '—'
        if metric_type == 'int':
            return f"{int(round(value))}"
        if metric_type == 'percent':
            return f"{value * 100:.1f}%"
        if metric_type == 'ops_plus':
            return f"{int(round(value))}"
        return f"{value:.3f}"

    def _format_diff(diff_value, metric_type: str) -> tuple[str, str]:
        if pd.isna(diff_value):
            return '—', 'even'

        if metric_type in {'int', 'ops_plus'}:
            diff_int = int(round(diff_value))
            if diff_int == 0:
                return '0', 'even'
            return f"{diff_int:+d}", 'positive' if diff_int > 0 else 'negative'

        if metric_type == 'percent':
            if abs(diff_value) < 0.0005:
                return '0.0 pts', 'even'
            return f"{diff_value * 100:+.1f} pts", 'positive' if diff_value > 0 else 'negative'

        if abs(diff_value) < 0.0005:
            return '0.000', 'even'
        return f"{diff_value:+.3f}", 'positive' if diff_value > 0 else 'negative'

    def _build_player_card(player_id: str, row: pd.Series) -> dict:
        return {
            'id': player_id,
            'name': row['player_name'],
            'badges_html': row['badges_html'],
            'badges_text': row['badges_text'],
            'hall_of_famer': bool(row['hall_of_famer']),
            'all_star': bool(row['all_star']),
            'slash_line': f"{_format_stat(row['avg'], 'rate')}/{_format_stat(row['obp'], 'rate')}/{_format_stat(row['slg'], 'rate')}",
            'ops_display': _format_stat(row['ops'], 'rate'),
            'ops_plus_display': _format_stat(row['ops_plus'], 'ops_plus'),
            'sb_pct_display': _format_stat(row['sb_pct'], 'percent'),
        }

    def _build_comparison(player_one_id: str, player_two_id: str):
        try:
            row_one = players_lookup.loc[player_one_id]
            row_two = players_lookup.loc[player_two_id]
        except KeyError:
            return [], []

        cards = [
            _build_player_card(player_one_id, row_one),
            _build_player_card(player_two_id, row_two),
        ]

        comparison_rows = []
        for key, label, metric_type in stat_config:
            value_one = row_one.get(key)
            value_two = row_two.get(key)
            display_one = _format_stat(value_one, metric_type)
            display_two = _format_stat(value_two, metric_type)
            if pd.isna(value_one) or pd.isna(value_two):
                diff_display, diff_class = '—', 'even'
            else:
                diff_val = value_one - value_two
                diff_display, diff_class = _format_diff(diff_val, metric_type)
            comparison_rows.append({
                'label': label,
                'player_one': display_one,
                'player_two': display_two,
                'difference': diff_display,
                'diff_class': diff_class,
            })
        return cards, comparison_rows

    comparison_ready = False
    player_cards: list[dict] = []
    comparison_rows: list[dict] = []

    if form.validate_on_submit():
        player_one_id = form.player_one.data
        player_two_id = form.player_two.data
        if player_one_id == player_two_id:
            form.player_two.errors.append('Choose a different player for comparison.')
        elif player_one_id not in players_lookup.index or player_two_id not in players_lookup.index:
            flash('Selected players could not be found.', 'danger')
        else:
            player_cards, comparison_rows = _build_comparison(player_one_id, player_two_id)
            if player_cards:
                comparison_ready = True
    elif request.method == 'GET' and preselected_one and preselected_two:
        if (
            preselected_one != preselected_two
            and preselected_one in players_lookup.index
            and preselected_two in players_lookup.index
        ):
            player_cards, comparison_rows = _build_comparison(preselected_one, preselected_two)
            if player_cards:
                comparison_ready = True

    return render_template(
        'compare.html',
        team=team,
        year_id=year_id,
        form=form,
        comparison_ready=comparison_ready,
        player_cards=player_cards,
        comparison_rows=comparison_rows,
        summary=summary,
    )
