"""Enforced input and SQL boundaries; database permissions remain mandatory."""
import math
import sqlglot
from sqlglot import exp

VIEW = 'FDE_VIEWS.VW_ACTIVE_FLEET'
COLUMNS = {'Timestamp', 'Latitude', 'Longitude', 'Current_Temperature_C',
           'Cargo_Condition_Code', 'Risk_Classification', 'Delay_Probability',
           'Port_Congestion_Level', 'Route_Risk_Index'}


def validate_input(value):
    if not isinstance(value, str) or not value.strip() or len(value) > 4000:
        raise ValueError('Enter between 1 and 4000 characters.')
    return value.strip()


def coordinates(latitude, longitude):
    if not all(math.isfinite(x) for x in (latitude, longitude)):
        raise ValueError('Coordinates must be finite.')
    if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
        raise ValueError('Coordinates are outside GPS bounds.')


def safe_sql(query):
    validate_input(query)
    statements = sqlglot.parse(query, read='tsql')
    if len(statements) != 1 or not isinstance(statements[0], exp.Select):
        raise ValueError('Only one SELECT against the fleet view is allowed.')
    tree = statements[0]
    allowed = {'expressions', 'from_', 'where', 'order', 'limit', 'offset', 'distinct'}
    if any(value and key not in allowed for key, value in tree.args.items()):
        raise ValueError('Unsupported SELECT clause.')
    # No subqueries, joins, CTEs, INTO, hints, functions or set operations.
    if len(list(tree.find_all(exp.Select))) != 1:
        raise ValueError('Nested queries are not allowed.')
    forbidden = (exp.Join, exp.With, exp.Into, exp.Command, exp.Subquery)
    if any(tree.find(t) is not None for t in forbidden) or list(tree.find_all(exp.Func)):
        raise ValueError('Use a simple fleet SELECT without functions, joins or INTO.')
    tables = list(tree.find_all(exp.Table))
    if len(tables) != 1 or tables[0].catalog or tables[0].db.upper() != 'FDE_VIEWS' or tables[0].name.upper() != 'VW_ACTIVE_FLEET':
        raise ValueError('Only FDE_VIEWS.VW_ACTIVE_FLEET is accessible.')
    if tables[0].args.get('hints'):
        raise ValueError('Table hints are not allowed.')
    for column in tree.find_all(exp.Column):
        if column.name.lower() not in {c.lower() for c in COLUMNS}:
            raise ValueError(f'Column is not allowed: {column.name}')
    # Replace any caller limit, including expressions, with a fixed result bound.
    tree.set('limit', exp.Limit(expression=exp.Literal.number(10)))
    tree.set('offset', None)
    for node in tree.walk():
        node.comments = None
    return tree
