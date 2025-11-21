from flask_wtf import FlaskForm
from wtforms import BooleanField, IntegerField, PasswordField, SelectField, StringField, SubmitField
from wtforms.validators import DataRequired, Email, EqualTo, Length, NumberRange


class RegisterForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=3, max=64)])
    email = StringField('Email', validators=[DataRequired(), Email(), Length(max=120)])
    password = PasswordField('Password', validators=[DataRequired()])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Create Account')


class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    remember = BooleanField('Remember me')
    submit = SubmitField('Sign In')


class TeamYearForm(FlaskForm):
    year = IntegerField(
        'Season Year',
        validators=[DataRequired(), NumberRange(min=1871, max=2024, message='Year must be between 1871 and 2024')],
    )
    team_id = SelectField('Team', choices=[], validators=[DataRequired(message='Select a team')], coerce=str)
    submit_load = SubmitField('Load Teams')
    submit_view = SubmitField('View Team')


class PlayerCompareForm(FlaskForm):
    player_one = SelectField('Player One', choices=[], validators=[DataRequired()], coerce=str)
    player_two = SelectField('Player Two', choices=[], validators=[DataRequired()], coerce=str)
    submit = SubmitField('Compare Players')


class TeamCompareForm(FlaskForm):
    year = IntegerField(
        'Season Year',
        validators=[DataRequired(), NumberRange(min=1871, max=2024, message='Year must be between 1871 and 2024')],
    )
    team_one = SelectField('Team One', choices=[], validators=[DataRequired()], coerce=str)
    team_two = SelectField('Team Two', choices=[], validators=[DataRequired()], coerce=str)
    submit_load = SubmitField('Load Teams')
    submit_compare = SubmitField('Compare Teams')
