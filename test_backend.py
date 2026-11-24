"""Integration checks for the authoritative SQL and final database diagram."""
from pathlib import Path
import re
import shutil
import sqlite3
import subprocess
import tempfile
import unittest

import database

ROOT = Path(__file__).resolve().parent


class BackendTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / 'fresh.db'
        database.initialize(self.path)
        self.db = database.connect(self.path)

    def tearDown(self):
        self.db.close()
        self.temp.cleanup()

    def test_schema_seed_view_and_indexes(self):
        expected = {'departments': 6, 'locations': 6, 'employees': 12,
                    'devices': 20, 'assignments': 16, 'incidents': 8, 'maintenance_records': 8}
        for table, count in expected.items():
            self.assertEqual(self.db.execute('SELECT COUNT(*) FROM ' + table).fetchone()[0], count)
        self.assertEqual(self.db.execute('PRAGMA foreign_keys').fetchone()[0], 1)
        self.assertEqual(self.db.execute('PRAGMA foreign_key_check').fetchall(), [])
        self.assertEqual(self.db.execute('PRAGMA integrity_check').fetchone()[0], 'ok')
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM v_device_accountability').fetchone()[0], 20)
        indexes = {r[0] for r in self.db.execute("SELECT name FROM sqlite_master WHERE type='index'")}
        self.assertIn('idx_assignments_employee_date', indexes)
        self.assertIn('ux_assignments_open_device', indexes)
        # Both authoritative scripts can also recreate the existing tables.
        self.db.executescript((ROOT / 'schema.sql').read_text(encoding='utf-8'))
        self.db.executescript((ROOT / 'insert_data.sql').read_text(encoding='utf-8'))
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM devices').fetchone()[0], 20)

    def test_all_nine_queries(self):
        pending = ''
        results = []
        for line in (ROOT / 'queries.sql').read_text(encoding='utf-8').splitlines(keepends=True):
            pending += line
            if sqlite3.complete_statement(pending):
                cursor = self.db.execute(pending)
                if cursor.description:
                    results.append([tuple(r) for r in cursor.fetchall()])
                pending = ''
        self.assertEqual([len(r) for r in results], [7, 4, 6, 2, 1, 1, 2, 4, 5])
        self.assertIn(('New Ventures', 0), results[2])
        self.assertEqual({r[2] for r in results[3]}, {'Jamie Wells', 'Avery Chen'})
        self.assertEqual(results[4], [(8, 7, 2, 7, 1, 215.0, 30.71)])
        self.assertEqual(results[5][0][:2], ('OPS-1011', 2))
        self.assertEqual({r[1] for r in results[6]}, {'Casey Brooks', 'Riley Patel'})
        self.assertEqual({r[0] for r in results[7]}, {5, 11, 12, 13})
        self.assertEqual({r[0] for r in results[8]}, {'FIN-1012', 'IT-1019', 'OPS-1005', 'OPS-1011', 'OPS-1013'})

    def test_transaction_rolls_back(self):
        before = '\n'.join(self.db.iterdump())
        self.db.executescript((ROOT / 'transaction.sql').read_text(encoding='utf-8'))
        self.assertEqual(before, '\n'.join(self.db.iterdump()))
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM assignments').fetchone()[0], 16)

    def test_diagram_matches_columns_and_optional_references(self):
        diagram = (ROOT / 'ERD.md').read_text(encoding='utf-8')
        entities = dict(re.findall(r'^    (\w+) \{\n(.*?)^    \}', diagram, re.M | re.S))
        tables = {r[0] for r in self.db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        self.assertEqual(set(entities), tables)
        for table in tables:
            columns = self.db.execute('PRAGMA table_info(' + table + ')').fetchall()
            documented = re.findall(r'^        (\w+) (\w+)(.*)$', entities[table], re.M)
            self.assertEqual([(r['type'], r['name']) for r in columns], [(t, n) for t, n, _ in documented])
            details = {n: extra for _, n, extra in documented}
            for column in columns:
                if not column['pk']:
                    self.assertIn('required' if column['notnull'] else 'optional', details[column['name']])
            for fk in self.db.execute('PRAGMA foreign_key_list(' + table + ')'):
                self.assertIn('FK', details[fk['from']])

    @unittest.skipUnless(shutil.which('bash') and shutil.which('sqlite3'), 'Bash/SQLite CLI not installed')
    def test_bash_recreation_twice_from_another_directory(self):
        folder = Path(self.temp.name) / 'submission'
        folder.mkdir()
        for name in ('schema.sql', 'insert_data.sql', 'queries.sql', 'transaction.sql', 'run_queries.sh'):
            shutil.copyfile(ROOT / name, folder / name)
        for _ in range(2):
            result = subprocess.run(['bash', str(folder / 'run_queries.sh')], cwd=self.temp.name,
                                    capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('AFTER rollback', result.stdout)
            self.assertIn('Done.', result.stdout)


if __name__ == '__main__':
    unittest.main()
