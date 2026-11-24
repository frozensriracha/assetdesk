"""Local Flask web application for IT asset accountability database."""
import argparse
from pathlib import Path
import secrets
import sqlite3

from flask import Flask, abort, flash, g, redirect, render_template, request, session, url_for
from werkzeug.exceptions import HTTPException

import database
import operations as ops


def create_app(database_path=None, testing=False):
    app = Flask(__name__)
    app.config.update(SECRET_KEY=secrets.token_hex(32), TESTING=testing,
                      DATABASE=str(Path(database_path or database.ROOT / 'asset_accountability.db').resolve()),
                      MAX_CONTENT_LENGTH=64 * 1024, SESSION_COOKIE_HTTPONLY=True,
                      SESSION_COOKIE_SAMESITE='Lax')

    def db():
        if 'db' not in g:
            g.db = database.connect(app.config['DATABASE'])
        return g.db

    @app.teardown_appcontext
    def close_db(error=None):
        connection = g.pop('db', None)
        if connection is not None:
            connection.close()

    @app.before_request
    def csrf_check():
        if 'csrf' not in session:
            session['csrf'] = secrets.token_hex(32)
        if request.method == 'POST' and not secrets.compare_digest(session['csrf'], request.form.get('csrf', '')):
            abort(400, description='The form expired. Reload the page and try again.')

    @app.after_request
    def security_headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Content-Security-Policy'] = "default-src 'self'; style-src 'self'; form-action 'self'; frame-ancestors 'none'"
        return response

    @app.errorhandler(ops.InputError)
    def invalid(error):
        return render_template('error.html', message=str(error)), 400

    @app.errorhandler(sqlite3.IntegrityError)
    def constraint(error):
        detail = str(error)
        if 'UNIQUE' in detail:
            message = 'That asset tag or serial number already exists, or the device already has an open assignment.'
        elif 'overlap' in detail:
            message = 'Those dates overlap another assignment. Check the device history and choose a later checkout time.'
        elif 'FOREIGN KEY' in detail:
            message = 'The selected employee, department, or location no longer exists. Reload the form and select again.'
        else:
            message = 'The change conflicts with the database rules. Check the dates and selected values.'
        return render_template('error.html', message=message), 409

    @app.errorhandler(sqlite3.Error)
    def database_error(error):
        app.logger.error('Database operation failed: %s', error)
        return render_template('error.html', message='The database is unavailable or busy. Try again shortly. If this continues, check the setup instructions.'), 503

    @app.errorhandler(HTTPException)
    def http_error(error):
        return render_template('error.html', message=error.description), error.code

    @app.errorhandler(500)
    def unexpected(error):
        return render_template('error.html', message='The operation could not be completed. Please try again.'), 500

    def choices():
        return dict(departments=db().execute('SELECT * FROM departments ORDER BY department_name').fetchall(),
                    locations=db().execute('SELECT * FROM locations ORDER BY location_name').fetchall(),
                    employees=db().execute("SELECT * FROM employees WHERE employment_status = 'ACTIVE' ORDER BY full_name").fetchall(),
                    types=ops.TYPES)

    @app.get('/')
    def inventory():
        search = request.args.get('q', '').strip()
        status = request.args.get('status', '')
        if len(search) > 120 or (status and status not in ops.STATUSES):
            raise ops.InputError('Use a search of at most 120 characters and a listed status.')
        try:
            page = int(request.args.get('page', '1'))
            if not 1 <= page <= 100000:
                raise ValueError
        except ValueError:
            raise ops.InputError('Invalid page number.') from None
        # gives a literal substring search, SQL wildcard characters are not special
        predicate = '''WHERE (? = '' OR instr(lower(asset_tag), lower(?)) > 0
            OR instr(lower(serial_number), lower(?)) > 0)
            AND (? = '' OR status = ?)'''
        args = (search, search, search, status, status)
        total = db().execute('SELECT COUNT(*) FROM v_device_accountability ' + predicate, args).fetchone()[0]
        rows = db().execute('SELECT * FROM v_device_accountability ' + predicate +
                            ' ORDER BY asset_tag LIMIT ? OFFSET ?', args + (25, (page - 1) * 25)).fetchall()
        return render_template('inventory.html', rows=rows, total=total, page=page,
                               search=search, status=status, statuses=ops.STATUSES)

    @app.route('/devices/new', methods=['GET', 'POST'])
    def register():
        if request.method == 'POST':
            device_id = ops.register(db(), request.form)
            flash('Device registered and ready for assignment.')
            return redirect(url_for('detail', device_id=device_id), code=303)
        return render_template('register.html', **choices())

    @app.get('/devices/<int:device_id>')
    def detail(device_id):
        if device_id > 9223372036854775807:
            abort(404)
        row = ops.device(db(), device_id)
        history = db().execute('''SELECT a.*, e.full_name, l.location_name
            FROM assignments a INNER JOIN employees e ON e.employee_id = a.employee_id
            LEFT JOIN locations l ON l.location_id = a.location_id
            WHERE a.device_id = ? ORDER BY a.assigned_at DESC, a.assignment_id DESC''', (device_id,)).fetchall()
        incidents = db().execute('SELECT * FROM incidents WHERE device_id = ? ORDER BY reported_at DESC', (device_id,)).fetchall()
        services = db().execute('''SELECT m.*, e.full_name AS technician FROM maintenance_records m
            LEFT JOIN employees e ON e.employee_id = m.technician_employee_id
            WHERE m.device_id = ? ORDER BY m.started_at DESC''', (device_id,)).fetchall()
        return render_template('detail.html', device=row, history=history, incidents=incidents,
                               services=services, now=ops.utc_now()[:16].replace(' ', 'T'), **choices())

    @app.post('/devices/<int:device_id>/<action>')
    def change(device_id, action):
        if device_id > 9223372036854775807:
            abort(404)
        actions = {'move': (ops.move, 'Expected location updated.'),
                   'checkout': (ops.checkout, 'Checkout saved. The device and assignment were updated together.'),
                   'return': (ops.checkin, 'Return saved. Damaged equipment and equipment with unresolved issues remain in maintenance.')}
        if action not in actions:
            abort(404)
        operation, message = actions[action]
        operation(db(), device_id, request.form)
        flash(message)
        return redirect(url_for('detail', device_id=device_id), code=303)

    @app.get('/reports')
    def reports():
        departments = db().execute('''SELECT dep.department_name, COUNT(d.device_id) AS total,
            SUM(CASE WHEN d.status = 'AVAILABLE' THEN 1 ELSE 0 END) AS available,
            SUM(CASE WHEN d.status = 'ASSIGNED' THEN 1 ELSE 0 END) AS assigned,
            SUM(CASE WHEN d.status IN ('MAINTENANCE', 'LOST') THEN 1 ELSE 0 END) AS attention
            FROM departments dep LEFT JOIN devices d ON d.department_id = dep.department_id
            GROUP BY dep.department_id, dep.department_name ORDER BY total DESC, dep.department_name''').fetchall()
        now = ops.utc_now()
        overdue = db().execute('''SELECT * FROM v_device_accountability
            WHERE due_back_at < ? ORDER BY due_back_at, asset_tag''', (now,)).fetchall()
        incidents = db().execute('''SELECT d.device_id, d.asset_tag, COUNT(*) AS total
            FROM devices d JOIN incidents i ON i.device_id = d.device_id
            GROUP BY d.device_id, d.asset_tag HAVING COUNT(*) >= 2 ORDER BY total DESC, d.asset_tag''').fetchall()
        return render_template('reports.html', departments=departments, overdue=overdue,
                               repeated=incidents, now=now)

    return app


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', type=Path, default=database.ROOT / 'asset_accountability.db')
    parser.add_argument('--init-db', action='store_true', help='Create sample database only; refuses to overwrite an existing file')
    parser.add_argument('--port', type=int, default=5000)
    args = parser.parse_args()
    try:
        if args.init_db:
            database.initialize(args.database)
            print(f'Created {args.database.resolve()}')
            return
        connection = database.connect(args.database)
        try:
            connection.execute('SELECT device_id FROM v_device_accountability LIMIT 1').fetchall()
        finally:
            connection.close()
    except (OSError, ValueError, sqlite3.Error) as error:
        parser.exit(1, f'Cannot open or initialize the database: {error}\nUse --init-db with a new filename for a fresh sample database.\n')
    create_app(args.database).run(host='127.0.0.1', port=args.port, debug=False)


if __name__ == '__main__':
    main()
