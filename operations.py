"""Validated, parameterized SQL operations. SQLite is only persistent store."""
from contextlib import contextmanager
from datetime import date, datetime, timezone

TYPES = ('LAPTOP', 'DESKTOP', 'TABLET', 'PHONE', 'MONITOR', 'PRINTER')
STATUSES = ('AVAILABLE', 'ASSIGNED', 'MAINTENANCE', 'LOST', 'RETIRED')


class InputError(ValueError):
    pass


def text(value, label, limit=120):
    value = (value or '').strip()
    if not value or len(value) > limit:
        raise InputError(f'{label} is required and must be at most {limit} characters.')
    return value


def number(value, label):
    try:
        result = int(value)
        if not 1 <= result <= 9223372036854775807:
            raise ValueError
        return result
    except (TypeError, ValueError):
        raise InputError(f'Choose a valid {label}.') from None


def timestamp(value, label):
    try:
        parsed = datetime.strptime(value, '%Y-%m-%dT%H:%M')
        return parsed.strftime('%Y-%m-%d %H:%M:%S')
    except (TypeError, ValueError):
        raise InputError(f'{label} must be a valid date and time.') from None


def utc_now():
    return datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')


def device(db, device_id):
    row = db.execute('SELECT * FROM v_device_accountability WHERE device_id = ?',
                     (device_id,)).fetchone()
    if row is None:
        raise InputError('That device was not found. Return to the inventory and select a device.')
    return row


@contextmanager
def transaction(db):
    # Acquire the writer lock before checking eligibility to prevent stale checkouts.
    db.execute('BEGIN IMMEDIATE')
    try:
        yield
        db.commit()
    except Exception:
        db.rollback()
        raise


def register(db, form):
    tag = text(form.get('asset_tag'), 'Asset tag')
    serial = text(form.get('serial_number'), 'Serial number')
    kind = form.get('device_type')
    if kind not in TYPES:
        raise InputError('Choose a valid device type.')
    department = number(form.get('department_id'), 'department')
    location = number(form.get('location_id'), 'location')
    purchased = form.get('purchase_date', '').strip() or None
    if purchased:
        try:
            if date.fromisoformat(purchased).isoformat() != purchased:
                raise ValueError
            if date.fromisoformat(purchased) > datetime.now(timezone.utc).date():
                raise ValueError
        except ValueError:
            raise InputError('Purchase date must be a real date, no later than today.') from None
    with transaction(db):
        result = db.execute('''INSERT INTO devices
            (asset_tag, serial_number, device_type, department_id, current_location_id, purchase_date)
            VALUES (?, ?, ?, ?, ?, ?)''', (tag, serial, kind, department, location, purchased))
        return result.lastrowid


def move(db, device_id, form):
    location = number(form.get('location_id'), 'location')
    with transaction(db):
        row = device(db, device_id)
        if row['status'] == 'LOST':
            raise InputError('Check the lost device back in before recording a new location.')
        db.execute('UPDATE devices SET current_location_id = ? WHERE device_id = ?', (location, device_id))


def checkout(db, device_id, form):
    employee = number(form.get('employee_id'), 'employee')
    issue_location = number(form.get('issue_location_id'), 'issue location')
    destination = number(form.get('location_id'), 'expected location')
    assigned = timestamp(form.get('assigned_at'), 'Checkout time')
    due = timestamp(form['due_back_at'], 'Due time') if form.get('due_back_at') else None
    if assigned > utc_now():
        raise InputError('Checkout time cannot be in the future.')
    if due and due <= assigned:
        raise InputError('Due time must be after checkout time.')
    with transaction(db):
        row = device(db, device_id)
        if (row['status'] != 'AVAILABLE' or row['assignment_id'] is not None
                or row['unresolved_incidents'] or row['open_service_records']):
            raise InputError('This device is not ready for checkout. It must be available with no open loan, incident, or service.')
        if not db.execute("SELECT 1 FROM employees WHERE employee_id = ? AND employment_status = 'ACTIVE'",
                          (employee,)).fetchone():
            raise InputError('Choose an active employee.')
        db.execute("UPDATE devices SET status = 'ASSIGNED', current_location_id = ? WHERE device_id = ?",
                   (destination, device_id))
        db.execute('''INSERT INTO assignments
            (employee_id, device_id, location_id, assigned_at, due_back_at)
            VALUES (?, ?, ?, ?, ?)''', (employee, device_id, issue_location, assigned, due))


def checkin(db, device_id, form):
    location = number(form.get('location_id'), 'return location')
    returned = timestamp(form.get('returned_at'), 'Return time')
    condition = form.get('return_condition')
    if condition not in ('GOOD', 'FAIR', 'DAMAGED'):
        raise InputError('Choose a valid return condition.')
    if returned > utc_now():
        raise InputError('Return time cannot be in the future.')
    with transaction(db):
        row = device(db, device_id)
        if row['assignment_id'] is None:
            raise InputError('This device has no open assignment to return.')
        if returned <= row['assigned_at']:
            raise InputError('Return time must be after checkout time (at least one minute later).')
        db.execute("""UPDATE assignments SET returned_at = ?, return_condition = ?,
            assignment_status = 'CLOSED' WHERE assignment_id = ?""",
                   (returned, condition, row['assignment_id']))
        # Existing unresolved issues must not become available inventory on return.
        status = 'MAINTENANCE' if (condition == 'DAMAGED' or row['unresolved_incidents']
                                    or row['open_service_records']) else 'AVAILABLE'
        db.execute('UPDATE devices SET status = ?, current_location_id = ? WHERE device_id = ?',
                   (status, location, device_id))
        if condition == 'DAMAGED':
            db.execute("""INSERT INTO incidents
                (device_id, reported_by_employee_id, incident_type, reported_at, details)
                VALUES (?, ?, 'DAMAGE', ?, 'Damage recorded during equipment return.')""",
                       (device_id, row['custodian_employee_id'], returned))
