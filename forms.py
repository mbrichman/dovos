from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, IntegerField
from wtforms.validators import DataRequired, Optional


class SearchForm(FlaskForm):
    query = StringField("Search Query", validators=[DataRequired()])
    results_count = IntegerField(
        "Number of Results", default=5, validators=[Optional()]
    )
    search_type = SelectField(
        "Search Type",
        choices=[("semantic", "Semantic Search"), ("keyword", "Keyword Search")],
        default="semantic",
    )
    date_from = StringField("From Date (YYYY-MM-DD)", validators=[Optional()])
    date_to = StringField("To Date (YYYY-MM-DD)", validators=[Optional()])