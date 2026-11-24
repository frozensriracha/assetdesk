# AssetDesk

AssetDesk is an IT asset and device accountability system for IT staff, asset managers, and department managers. Its Python/Flask web application uses SQLite to track equipment, ownership, expected locations, employee custody, incidents, and maintenance history.

## Requirements and download

Use Python 3.10 or newer with SQLite 3.37 or newer (required by STRICT tables), Flask 3.1.2, and a web browser. Flask and its dependencies are installed from `requirements.txt`. No hosted account, database server, password, API key, or `.env` file is needed. SQLite is included with Python. Only the optional Bash demonstration requires Bash and the SQLite command-line program, version 3.37 or newer.

```text
git clone https://github.com/frozensriracha/assetdesk.git
cd assetdesk
```

Alternatively, download and extract GitHub's ZIP. Run the following commands from the extracted project folder.

## Windows setup (PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe app.py --database demo.db --init-db
.\.venv\Scripts\python.exe app.py --database demo.db
```

If your installation uses the Python launcher, use `py -3 -m venv .venv` for the first command. Environment activation is not required.

## macOS, Linux, or WSL setup (Bash)

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python app.py --database demo.db --init-db
.venv/bin/python app.py --database demo.db
```

If Ubuntu reports missing `ensurepip`, run `sudo apt-get install python3-venv`, then retry. Check Python's SQLite version with `python -c "import sqlite3; print(sqlite3.sqlite_version)"` (use `python3` on Linux). If it is older than 3.37, use a newer Python build.

Open **http://127.0.0.1:5000**. Stop the application with **Ctrl+C**. On later runs, use only the final command: omit `--init-db` to keep saved changes. Initialization refuses to overwrite an existing file. Use a new filename for another fresh demonstration database.

## Database setup and configuration

The DBMS is **SQLite**. Initialization executes `schema.sql` first and `insert_data.sql` second, then checks foreign-key relationships. These files are authoritative; no existing database file is required. The seed contains 76 synthetic rows: 6 departments, 6 locations, 12 employees, 20 devices, 16 assignments, 8 incidents, and 8 maintenance records.

`--database PATH` selects the persistent SQLite file. Relative paths are resolved from the terminal's current directory. Without the option, the app expects `asset_accountability.db` beside `app.py`. Append `--port 5001` to use http://127.0.0.1:5001. These command-line arguments are the complete configuration. No environment settings or credentials need to be supplied.

Every application connection enables `PRAGMA foreign_keys = ON`. SQL files also enable it before their transactions. When using another database client, enable it on each new connection before beginning a transaction.

The [final ER diagram](ERD.md) documents all tables, columns, and relationship optionality. The schema enforces required values, unique tags/serials/emails, allowed codes, dates, chronological assignments, and nonnegative costs. A partial unique index prevents two open loans for a device; triggers prevent overlapping custody intervals. Explicit indexes support department inventory, employee/device history, incidents, and maintenance. The `v_device_accountability` view combines ownership, locations, current custody, and unresolved incident/service counts.

## Application operations

| Operation | Access | Database behavior |
| --- | --- | --- |
| Search/browse | Inventory search and status filter | SQL filtering, sorting, counting, and pagination |
| Related history | Click an asset tag | Joins retrieve assignment employees/locations and maintenance technicians |
| Register equipment | Register device | INSERT with uniqueness and foreign-key validation |
| Update location | Device page → Update expected location | UPDATE the expected location |
| Reports | Reports navigation link | Department aggregates, overdue loans through the view, repeated incidents using GROUP BY/HAVING |
| Checkout | Available device → Check out to an employee | Transaction updates the device and inserts its assignment |
| Return | Assigned device → Check device back in | Transaction closes custody and updates the device; damaged returns also insert an incident |

All user-supplied SQL values are parameterized. The app validates required fields, IDs, types, dates, and checkout eligibility. Constraints provide additional enforcement. Rejected requests show readable messages; use the browser's Back button to correct a form. Connections close after each request, and multi-step changes commit or roll back together.

## Demonstration walkthrough

Start with a fresh `demo.db`. Search for IT-1009 and open its history: Jamie Wells and Avery Chen were previous custodians. Open Reports: New Ventures owns zero devices, and OPS-1011 has repeated incidents.

Register a laptop with a new asset tag and serial, owning department, and location. Update its location, then check it out to Robin Hayes. Set checkout time to at least ten minutes ago and an optional due time later than checkout. Check it back in with a return time after checkout but no later than now. A good return becomes available unless unresolved issues remain; a damaged return records an incident and becomes maintenance. Restart without initialization to verify persistence. Try registering the same tag again to see duplicate validation.

All entered times are **UTC**, with minute precision. A return must be in a later minute than checkout. Checkout requires an active employee and an available device with no open assignment, unresolved incident, or unfinished service.

## SQL queries and transaction

`queries.sql` contains nine separately numbered reports: filtering/sorting, INNER JOIN, LEFT JOIN, a three-table join, aggregates, GROUP BY/HAVING, a subquery, UNION, and the view. SQL overdue reports use **2026-11-02 00:00:00 UTC** for reproducible grading; application reports use the current UTC time.

`transaction.sql` checks out IT-1009 to Robin Hayes by changing both device and assignment records. It displays before/during/after state, then rolls back so the sample remains unchanged. Run it against fresh sample data.

With Bash and SQLite CLI installed:

```bash
bash run_queries.sh
```

This **replaces `asset_accountability.db` in the script's directory**, checks integrity/foreign keys, and runs schema → seed → queries → transaction. It leaves `demo.db` alone. Do not use it on a database containing work you want to keep.

Alternatively, this SQLite CLI command works in PowerShell or Bash and replaces the project tables in `sql_demo.db`:

```text
sqlite3 -bail -header -column sql_demo.db ".read schema.sql" ".read insert_data.sql" ".read queries.sql" ".read transaction.sql"
```

## Automated evaluation

Windows:

```powershell
.\.venv\Scripts\python.exe -m unittest -v
```

macOS/Linux/WSL:

```bash
.venv/bin/python -m unittest -v
```

Tests recreate disposable databases from the submitted SQL without touching your working database. They verify HTTP startup, all operations, persistence across application instances, reports, invalid input, duplicate values, foreign keys, escaped output, CSRF, connection closure, and rollback after forced failures. Backend tests cover all nine queries, sample counts, views/indexes, recreation, and transaction restoration. The Bash test runs when Bash and the SQLite CLI are available; otherwise it is explicitly skipped.

## Files and consistency

`app.py` handles HTTP routes; `operations.py` handles validation and transactional SQL; `database.py` handles connections and setup. `templates/` and `static/` supply the interface. `test_app.py` and `test_backend.py` provide verification. `ERD.md` is the final diagram, rendered by GitHub. `README_APP.md` points to these final instructions.

The final application, schema, and seed retain the supplied `app-submission` versions. Missing SQL demonstrations and tests were brought in from the preceding project stage. Query headings were numbered for grading. The final diagram clarifies existing optional references and NOT NULL fields; no schema migration was needed.

Generated databases, virtual environments, caches, and credential files are excluded by `.gitignore`. Sample data is synthetic. The session signing key is generated at startup; restarting requires reloading open forms. No sensitive credentials are needed or included.

## Limitations

This local coursework app binds to `127.0.0.1` with debug disabled. It has no login or roles and is not configured for public hosting. It displays incident/service history but has no maintenance-resolution workflow; unresolved issues keep equipment unavailable. Employee/department administration is outside the current interface. There are no known blocking problems in the tested setup and supported operations. Overdue results depend on the report date as explained above.
