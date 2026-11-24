-- SQLite 3.37+ (STRICT tables). Run this before insert_data.sql.
-- Foreign-key enforcement is connection-specific. Enable it before BEGIN.
PRAGMA foreign_keys = ON;
BEGIN TRANSACTION;

DROP VIEW IF EXISTS v_device_accountability;
DROP TABLE IF EXISTS maintenance_records;
DROP TABLE IF EXISTS incidents;
DROP TABLE IF EXISTS assignments;
DROP TABLE IF EXISTS devices;
DROP TABLE IF EXISTS employees;
DROP TABLE IF EXISTS locations;
DROP TABLE IF EXISTS departments;

CREATE TABLE departments (
    department_id INTEGER PRIMARY KEY,
    department_name TEXT NOT NULL UNIQUE CHECK (length(trim(department_name)) > 0),
    manager_name TEXT
) STRICT;

CREATE TABLE locations (
    location_id INTEGER PRIMARY KEY,
    location_name TEXT NOT NULL CHECK (length(trim(location_name)) > 0),
    address TEXT,
    location_type TEXT CHECK (location_type IN ('OFFICE', 'STORAGE', 'REMOTE', 'SERVICE_CENTER'))
) STRICT;

CREATE TABLE employees (
    employee_id INTEGER PRIMARY KEY,
    department_id INTEGER NOT NULL REFERENCES departments(department_id) ON DELETE RESTRICT,
    full_name TEXT NOT NULL CHECK (length(trim(full_name)) > 0),
    email TEXT NOT NULL COLLATE NOCASE UNIQUE
        CHECK (email LIKE '%_@_%._%' AND instr(email, ' ') = 0),
    employment_status TEXT NOT NULL DEFAULT 'ACTIVE'
        CHECK (employment_status IN ('ACTIVE', 'ON_LEAVE', 'INACTIVE'))
) STRICT;

CREATE TABLE devices (
    device_id INTEGER PRIMARY KEY,
    department_id INTEGER NOT NULL REFERENCES departments(department_id) ON DELETE RESTRICT,
    current_location_id INTEGER REFERENCES locations(location_id) ON DELETE RESTRICT,
    asset_tag TEXT NOT NULL UNIQUE CHECK (length(trim(asset_tag)) > 0),
    serial_number TEXT NOT NULL UNIQUE CHECK (length(trim(serial_number)) > 0),
    device_type TEXT NOT NULL CHECK (device_type IN ('LAPTOP', 'DESKTOP', 'TABLET', 'PHONE', 'MONITOR', 'PRINTER')),
    status TEXT NOT NULL DEFAULT 'AVAILABLE'
        CHECK (status IN ('AVAILABLE', 'ASSIGNED', 'MAINTENANCE', 'LOST', 'RETIRED')),
    purchase_date TEXT CHECK (length(purchase_date) = 10
        AND date(purchase_date, '+0 days') IS purchase_date)
) STRICT;

-- Dates use YYYY-MM-DD; timestamps use UTC YYYY-MM-DD HH:MM:SS.
CREATE TABLE assignments (
    assignment_id INTEGER PRIMARY KEY,
    employee_id INTEGER NOT NULL REFERENCES employees(employee_id) ON DELETE RESTRICT,
    device_id INTEGER NOT NULL REFERENCES devices(device_id) ON DELETE RESTRICT,
    location_id INTEGER REFERENCES locations(location_id) ON DELETE RESTRICT,
    assigned_at TEXT NOT NULL CHECK (length(assigned_at) = 19
        AND datetime(assigned_at, '+0 days') IS assigned_at),
    due_back_at TEXT CHECK (length(due_back_at) = 19
        AND datetime(due_back_at, '+0 days') IS due_back_at),
    returned_at TEXT CHECK (length(returned_at) = 19
        AND datetime(returned_at, '+0 days') IS returned_at),
    assignment_status TEXT NOT NULL DEFAULT 'OPEN' CHECK (assignment_status IN ('OPEN', 'CLOSED')),
    return_condition TEXT CHECK (return_condition IN ('GOOD', 'FAIR', 'DAMAGED')),
    CHECK (due_back_at >= assigned_at),
    CHECK (returned_at > assigned_at),
    CHECK ((assignment_status = 'OPEN' AND returned_at IS NULL AND return_condition IS NULL)
        OR (assignment_status = 'CLOSED' AND returned_at IS NOT NULL))
) STRICT;

CREATE TABLE incidents (
    incident_id INTEGER PRIMARY KEY,
    device_id INTEGER NOT NULL REFERENCES devices(device_id) ON DELETE RESTRICT,
    reported_by_employee_id INTEGER REFERENCES employees(employee_id) ON DELETE RESTRICT,
    incident_type TEXT NOT NULL CHECK (incident_type IN ('LOSS', 'THEFT', 'DAMAGE', 'MALFUNCTION')),
    reported_at TEXT NOT NULL CHECK (length(reported_at) = 19
        AND datetime(reported_at, '+0 days') IS reported_at),
    details TEXT,
    resolved_at TEXT CHECK (length(resolved_at) = 19
        AND datetime(resolved_at, '+0 days') IS resolved_at),
    CHECK (resolved_at >= reported_at)
) STRICT;

CREATE TABLE maintenance_records (
    maintenance_id INTEGER PRIMARY KEY,
    device_id INTEGER NOT NULL REFERENCES devices(device_id) ON DELETE RESTRICT,
    technician_employee_id INTEGER REFERENCES employees(employee_id) ON DELETE RESTRICT,
    service_type TEXT NOT NULL CHECK (service_type IN ('REPAIR', 'INSPECTION', 'UPGRADE', 'PREVENTIVE')),
    started_at TEXT NOT NULL CHECK (length(started_at) = 19
        AND datetime(started_at, '+0 days') IS started_at),
    completed_at TEXT CHECK (length(completed_at) = 19
        AND datetime(completed_at, '+0 days') IS completed_at),
    notes TEXT,
    cost_cents INTEGER CHECK (cost_cents >= 0),
    CHECK (completed_at >= started_at)
) STRICT;

-- Enforces exclusive current custody
CREATE UNIQUE INDEX ux_assignments_open_device ON assignments(device_id)
    WHERE assignment_status = 'OPEN';
-- Employee loan history
CREATE INDEX idx_assignments_employee_date ON assignments(employee_id, assigned_at);
CREATE INDEX idx_assignments_device_date ON assignments(device_id, assigned_at);
CREATE INDEX idx_devices_department ON devices(department_id);
CREATE INDEX idx_incidents_device_resolution ON incidents(device_id, resolved_at);
CREATE INDEX idx_maintenance_device_date ON maintenance_records(device_id, started_at);

CREATE TRIGGER assignments_no_overlap_insert BEFORE INSERT ON assignments
BEGIN
    SELECT RAISE(ABORT, 'Device assignment intervals must not overlap')
    WHERE EXISTS (SELECT 1 FROM assignments a WHERE a.device_id = NEW.device_id
        AND (a.returned_at IS NULL OR NEW.assigned_at < a.returned_at)
        AND (NEW.returned_at IS NULL OR a.assigned_at < NEW.returned_at));
END;
CREATE TRIGGER assignments_no_overlap_update BEFORE UPDATE ON assignments
BEGIN
    SELECT RAISE(ABORT, 'Device assignment intervals must not overlap')
    WHERE EXISTS (SELECT 1 FROM assignments a WHERE a.device_id = NEW.device_id
        AND a.assignment_id <> OLD.assignment_id
        AND (a.returned_at IS NULL OR NEW.assigned_at < a.returned_at)
        AND (NEW.returned_at IS NULL OR a.assigned_at < NEW.returned_at));
END;

CREATE VIEW v_device_accountability AS
SELECT d.device_id, d.asset_tag, d.serial_number, d.device_type, d.status,
       dep.department_name AS owning_department,
       loc.location_name AS expected_location,
       a.assignment_id, e.employee_id AS custodian_employee_id,
       e.full_name AS custodian_name, e.email AS custodian_email,
       a.assigned_at, a.due_back_at,
       issue.location_name AS issued_at_location,
       (SELECT count(*) FROM incidents i
        WHERE i.device_id = d.device_id AND i.resolved_at IS NULL) AS unresolved_incidents,
       (SELECT count(*) FROM maintenance_records m
        WHERE m.device_id = d.device_id AND m.completed_at IS NULL) AS open_service_records
FROM devices d
JOIN departments dep ON dep.department_id = d.department_id
LEFT JOIN locations loc ON loc.location_id = d.current_location_id
LEFT JOIN assignments a ON a.device_id = d.device_id AND a.assignment_status = 'OPEN'
LEFT JOIN employees e ON e.employee_id = a.employee_id
LEFT JOIN locations issue ON issue.location_id = a.location_id;

COMMIT;

