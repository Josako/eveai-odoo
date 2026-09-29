"""Notification decision rules, free of Odoo imports.

The "who gets notified about what" logic in one place: the models gather
the values, these functions decide.
"""

#: Context keys that silence notifications for a whole operation. Evie's own
#: sync context (``evie_skip_phase_event`` / ``evie_skip_activity_event``) is
#: deliberately NOT listed: an assignment or a finished Evie action coming
#: from the sync is exactly what the rep should hear about.
MUTE_CONTEXT_KEYS = (
    'evie_skip_notifications',
    'import_file',
    'install_mode',
    'tracking_disable',
)

#: Qualification score from which a lead counts as hot (same threshold as the
#: green colour band on the Evie Lead Pipeline cards).
HOT_LEAD_SCORE = 70

#: Local hour from which the daily activity digest may be sent.
DIGEST_HOUR = 7

#: Evie action statuses that end a run (see crm.lead x_evie_action_status).
ACTION_FINISHED_STATUSES = ('DONE', 'FAILED')


def is_muted(context):
    """True when the operation's context asks for silence."""
    return any(context.get(key) for key in MUTE_CONTEXT_KEYS)


def lead_change_events(old_owner_id, new_owner_id, old_stage_id, new_stage_id):
    """Events for the lead owner caused by one write.

    A new owner hears about the assignment only (not also about a stage
    change in the same save); an unchanged owner hears about stage moves.
    Leads without an owner produce nothing.
    """
    if not new_owner_id:
        return []
    if new_owner_id != old_owner_id:
        return ['assigned']
    if new_stage_id != old_stage_id:
        return ['stage']
    return []


def crossed_hot_threshold(old_score, new_score, threshold=HOT_LEAD_SCORE):
    """True only when the score moves from below the threshold to at/above it."""
    return (old_score or 0) < threshold <= (new_score or 0)


def due_digest_counts(deadlines, today):
    """Count overdue and due-today dates for one user's open activities."""
    overdue = sum(1 for deadline in deadlines if deadline and deadline < today)
    due_today = sum(1 for deadline in deadlines if deadline == today)
    return overdue, due_today


def digest_due(local_hour, overdue, due_today, digest_hour=DIGEST_HOUR):
    """True when the daily digest should go out now for this user."""
    return local_hour >= digest_hour and bool(overdue or due_today)
