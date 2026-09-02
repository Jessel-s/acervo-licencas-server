from datetime import datetime


def parse_datetime_value(value):
    """Convert stored ISO datetime values to datetime objects."""
    if isinstance(value, datetime):
        return value
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None


def schedule_start(data_uso, hora_inicio):
    """Build the requested schedule start datetime."""
    hours, minutes = (int(part) for part in hora_inicio.split(':'))
    return datetime.strptime(data_uso, '%Y-%m-%d').replace(
        hour=hours, minute=minutes
    )


def is_available_after_return(data_uso, hora_inicio, previsao_devolucao):
    """Return whether an item is available at the requested schedule start."""
    requested_start = schedule_start(data_uso, hora_inicio)
    predicted_return = parse_datetime_value(previsao_devolucao)
    return bool(predicted_return and requested_start >= predicted_return)
