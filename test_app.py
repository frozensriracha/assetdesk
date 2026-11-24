"""Run with: python -m unittest -v test_app (uses disposable fresh databases)."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sqlite3
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.request import urlopen

from werkzeug.serving import make_server
from app import create_app
import database


class ApplicationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / 'test.db'
        database.initialize(self.path)
        self.app = create_app(self.path, testing=True)
        self.client = self.app.test_client()
        self.client.get('/')

    def tearDown(self):
        self.temp.cleanup()

    def post(self, path, **data):
        with self.client.session_transaction() as session:
            token = session['csrf']
        return self.client.post(path, data=dict(csrf=token, **data))

    def row(self, sql, args=()):
        db = database.connect(self.path)
        try:
            return db.execute(sql, args).fetchone()
        finally:
            db.close()

    def execute(self, sql):
        db = database.connect(self.path)
        try:
            db.executescript(sql)
        finally:
            db.close()

    def checkout_data(self):
        now = datetime.now(timezone.utc)
        return dict(employee_id='12', issue_location_id='1', location_id='2',
                    assigned_at=(now - timedelta(minutes=10)).strftime('%Y-%m-%dT%H:%M'),
                    due_back_at=(now + timedelta(days=7)).strftime('%Y-%m-%dT%H:%M'))

    def return_data(self, condition='GOOD'):
        return dict(location_id='1', return_condition=condition,
                    returned_at=(datetime.now(timezone.utc) - timedelta(minutes=1)).strftime('%Y-%m-%dT%H:%M'))

    def new_data(self):
        return dict(asset_tag='IT-TEST', serial_number='TEST-SERIAL', device_type='LAPTOP',
                    department_id='1', location_id='1', purchase_date='2026-01-01')

    def test_search_filter_and_empty_results(self):
        result = self.client.get('/?q=IT-1009&status=AVAILABLE')
        self.assertEqual(result.status_code, 200)
        self.assertIn(b'IT-1009', result.data)
        self.assertNotIn(b'FIN-1002', result.data)
        self.assertIn(b'No devices match', self.client.get('/?q=not-present').data)
        self.assertIn(b'No devices match', self.client.get('/?q=%27%20OR%201=1--').data)
        self.assertEqual(self.client.get('/?page=oops').status_code, 400)
        self.assertEqual(self.client.get('/?status=BOGUS').status_code, 400)

    def test_related_history(self):
        response = self.client.get('/devices/9')
        for value in (b'Jamie Wells', b'Avery Chen', b'North field office', b'Updated wireless driver'):
            self.assertIn(value, response.data)
        self.assertEqual(self.client.get('/devices/9999').status_code, 400)

    def test_all_forms_and_styles_serve(self):
        for path, expected in [('/devices/new', b'Purchase date'),
                               ('/devices/1', b'Confirm return'),
                               ('/devices/9', b'Confirm checkout'),
                               ('/devices/13', b'Check device back in'),
                               ('/static/style.css', b'font-family')]:
            result = self.client.get(path)
            self.assertEqual(result.status_code, 200, path)
            self.assertIn(expected, result.data)
            result.close()

    def test_register_persistence_and_duplicate(self):
        self.assertEqual(self.post('/devices/new', **self.new_data()).status_code, 303)
        device = self.row('SELECT * FROM devices WHERE asset_tag = ?', ('IT-TEST',))
        self.assertEqual(device['status'], 'AVAILABLE')
        second_app = create_app(self.path, testing=True)
        self.assertIn(b'IT-TEST', second_app.test_client().get('/?q=IT-TEST').data)
        response = self.post('/devices/new', **self.new_data())
        self.assertEqual(response.status_code, 409)
        self.assertIn(b'already exists', response.data)

    def test_registration_validation_and_escaping(self):
        for field, value in [('asset_tag', ' '), ('device_type', 'BOGUS'),
                             ('department_id', '-1'), ('location_id', 'text'),
                             ('purchase_date', '2026-02-30'), ('purchase_date', '2999-01-01')]:
            data = self.new_data()
            data[field] = value
            self.assertEqual(self.post('/devices/new', **data).status_code, 400, field)
        data = self.new_data()
        data['department_id'] = '9999'
        self.assertEqual(self.post('/devices/new', **data).status_code, 409)
        data = self.new_data()
        data['asset_tag'] = '<script>alert(1)</script>'
        result = self.post('/devices/new', **data)
        self.assertEqual(result.status_code, 303)
        html = self.client.get(result.location).data
        self.assertIn(b'&lt;script&gt;', html)
        self.assertNotIn(b'<script>', html)

    def test_move(self):
        self.assertEqual(self.post('/devices/9/move', location_id='4').status_code, 303)
        self.assertEqual(self.row('SELECT current_location_id FROM devices WHERE device_id=9')[0], 4)
        self.assertEqual(self.post('/devices/9/move', location_id='999').status_code, 409)
        self.assertEqual(self.row('SELECT current_location_id FROM devices WHERE device_id=9')[0], 4)

    def test_checkout_and_return(self):
        self.assertEqual(self.post('/devices/9/checkout', **self.checkout_data()).status_code, 303)
        self.assertEqual(self.row('SELECT status FROM devices WHERE device_id=9')[0], 'ASSIGNED')
        self.assertEqual(self.row("SELECT employee_id FROM assignments WHERE device_id=9 AND assignment_status='OPEN'")[0], 12)
        self.assertEqual(self.post('/devices/9/checkout', **self.checkout_data()).status_code, 400)
        self.assertEqual(self.post('/devices/9/return', **self.return_data()).status_code, 303)
        self.assertEqual(self.row('SELECT status FROM devices WHERE device_id=9')[0], 'AVAILABLE')
        self.assertEqual(self.row("SELECT count(*) FROM assignments WHERE device_id=9 AND assignment_status='OPEN'")[0], 0)
        self.assertEqual(self.post('/devices/9/return', **self.return_data()).status_code, 400)

    def test_damaged_return_creates_incident(self):
        self.post('/devices/9/checkout', **self.checkout_data())
        self.assertEqual(self.post('/devices/9/return', **self.return_data('DAMAGED')).status_code, 303)
        self.assertEqual(self.row('SELECT status FROM devices WHERE device_id=9')[0], 'MAINTENANCE')
        self.assertEqual(self.row("SELECT count(*) FROM incidents WHERE device_id=9 AND incident_type='DAMAGE' AND resolved_at IS NULL")[0], 1)
        self.assertEqual(self.post('/devices/9/checkout', **self.checkout_data()).status_code, 400)

    def test_return_validation_and_unresolved_issue(self):
        self.post('/devices/9/checkout', **self.checkout_data())
        for field, value in [('return_condition', 'BOGUS'), ('returned_at', 'bad-time'),
                             ('returned_at', '2020-01-01T12:00'), ('returned_at', '2999-01-01T12:00')]:
            data = self.return_data()
            data[field] = value
            self.assertEqual(self.post('/devices/9/return', **data).status_code, 400)
        self.assertEqual(self.row('SELECT status FROM devices WHERE device_id=9')[0], 'ASSIGNED')
        self.assertEqual(self.post('/devices/13/return', **self.return_data()).status_code, 303)
        self.assertEqual(self.row('SELECT status FROM devices WHERE device_id=13')[0], 'MAINTENANCE')

    def test_checkout_validation(self):
        data = self.checkout_data()
        data['employee_id'] = '9'  # inactive employee
        self.assertEqual(self.post('/devices/9/checkout', **data).status_code, 400)
        data = self.checkout_data()
        data['due_back_at'] = '2020-01-01T12:00'
        self.assertEqual(self.post('/devices/9/checkout', **data).status_code, 400)
        data = self.checkout_data()
        data['assigned_at'] = '2999-01-01T12:00'
        self.assertEqual(self.post('/devices/9/checkout', **data).status_code, 400)
        data = self.checkout_data()
        data['assigned_at'] = '2025-10-01T12:00'  # overlaps old history
        self.assertEqual(self.post('/devices/9/checkout', **data).status_code, 409)
        self.assertEqual(self.row('SELECT status FROM devices WHERE device_id=9')[0], 'AVAILABLE')

    def test_transaction_failure_rolls_back_both_operations(self):
        self.execute("""CREATE TRIGGER fail_checkout BEFORE INSERT ON assignments
            BEGIN SELECT RAISE(ABORT, 'forced failure'); END;""")
        self.assertEqual(self.post('/devices/9/checkout', **self.checkout_data()).status_code, 409)
        row = self.row('SELECT status, current_location_id FROM devices WHERE device_id=9')
        self.assertEqual(tuple(row), ('AVAILABLE', 1))
        self.execute('DROP TRIGGER fail_checkout;')
        self.post('/devices/9/checkout', **self.checkout_data())
        self.execute("""CREATE TRIGGER fail_return BEFORE UPDATE ON devices
            BEGIN SELECT RAISE(ABORT, 'forced failure'); END;""")
        self.assertEqual(self.post('/devices/9/return', **self.return_data()).status_code, 409)
        self.assertEqual(self.row("SELECT count(*) FROM assignments WHERE device_id=9 AND assignment_status='OPEN'")[0], 1)

    def test_reports(self):
        result = self.client.get('/reports')
        self.assertEqual(result.status_code, 200)
        for text in (b'New Ventures', b'Overdue equipment', b'Casey Brooks', b'OPS-1011', b'Repeated incidents'):
            self.assertIn(text, result.data)

    def test_csrf_and_large_ids(self):
        self.assertEqual(self.client.post('/devices/new', data=self.new_data()).status_code, 400)
        self.assertEqual(self.client.get('/devices/99999999999999999999999').status_code, 404)

    def test_connections_are_closed_and_foreign_keys_enabled(self):
        connections = []
        real_connect = database.connect

        def track(path):
            connection = real_connect(path)
            self.assertEqual(connection.execute('PRAGMA foreign_keys').fetchone()[0], 1)
            connections.append(connection)
            return connection

        with patch('database.connect', side_effect=track):
            self.client.get('/')
            self.post('/devices/new', **self.new_data())
        for connection in connections:
            with self.assertRaises(sqlite3.ProgrammingError):
                connection.execute('SELECT 1')

    def test_database_unavailable_friendly_error(self):
        app = create_app(Path(self.temp.name) / 'missing.db', testing=True)
        result = app.test_client().get('/')
        self.assertEqual(result.status_code, 503)
        self.assertIn(b'database is unavailable', result.data)
        self.assertNotIn(b'Traceback', result.data)

    def test_setup_refuses_overwrite(self):
        before = self.path.read_bytes()
        with self.assertRaises(FileExistsError):
            database.initialize(self.path)
        self.assertEqual(before, self.path.read_bytes())

    def test_real_http_startup(self):
        server = make_server('127.0.0.1', 0, self.app)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with urlopen(f'http://127.0.0.1:{server.server_port}/', timeout=5) as response:
                self.assertEqual(response.status, 200)
                self.assertIn(b'AssetDesk', response.read())
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)


if __name__ == '__main__':
    unittest.main()
