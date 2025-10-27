from flask import Blueprint, flash, redirect, render_template, request, url_for
from sqlalchemy import text
import pandas as pd

from . import db
from .forms import TeamYearForm
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


def _team_batting(team_id: str, year_id: int):
    with db.engine.connect() as connection:
        dataframe = pd.read_sql_query(
            text(queries.TEAM_BATTING),
            connection,
            params={'teamId': team_id, 'yearId': year_id},
        )
    return dataframe


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

    batting_df = _team_batting(team_id, year_id)
    if batting_df.empty:
        message = f"No batting stats available for team {team_id} in {year_id}."
        return render_template('error.html', message=message), 404

    batting_df = batting_df.rename(columns={
        'player_name': 'Player',
        'at_bats': 'At Bats',
        'hits': 'Hits',
        'home_runs': 'Home Runs',
        'runs_batted_in': 'RBIs',
        'walks': 'Walks',
        'strikeouts': 'Strikeouts',
    })
    table_html = batting_df.to_html(classes='data-table', index=False, border=0)

    return render_template(
        'team.html',
        team=team,
        year_id=year_id,
        table_html=table_html,
    )
