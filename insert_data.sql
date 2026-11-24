-- Run after schema.sql
PRAGMA foreign_keys = ON;
BEGIN TRANSACTION;

INSERT INTO departments (department_id, department_name, manager_name) VALUES
 (1, 'Information Technology', 'Morgan Reed'),
 (2, 'Finance', 'Avery Chen'),
 (3, 'Human Resources', 'Jordan Blake'),
 (4, 'Field Operations', 'Casey Brooks'),
 (5, 'Research', 'Taylor Ellis'),
 (6, 'New Ventures', NULL);

INSERT INTO locations (location_id, location_name, address, location_type) VALUES
 (1, 'Headquarters - IT stockroom', '100 Example Avenue, Sample City', 'STORAGE'),
 (2, 'Headquarters - second floor', '100 Example Avenue, Sample City', 'OFFICE'),
 (3, 'North field office', '200 Demonstration Road, Sample City', 'OFFICE'),
 (4, 'Remote work location', NULL, 'REMOTE'),
 (5, 'Contract repair depot', '300 Fictional Lane, Sample City', 'SERVICE_CENTER'),
 (6, 'Research laboratory', '400 Sample Boulevard, Sample City', 'OFFICE');

INSERT INTO employees (employee_id, department_id, full_name, email, employment_status) VALUES
 (1, 1, 'Morgan Reed', 'morgan.reed@example.com', 'ACTIVE'),
 (2, 1, 'Sam Rivera', 'sam.rivera@example.com', 'ACTIVE'),
 (3, 2, 'Avery Chen', 'avery.chen@example.com', 'ACTIVE'),
 (4, 2, 'Riley Patel', 'riley.patel@example.com', 'ACTIVE'),
 (5, 3, 'Jordan Blake', 'jordan.blake@example.com', 'ACTIVE'),
 (6, 3, 'Drew Sutton', 'drew.sutton@example.com', 'ON_LEAVE'),
 (7, 4, 'Casey Brooks', 'casey.brooks@example.com', 'ACTIVE'),
 (8, 4, 'Alex Quinn', 'alex.quinn@example.com', 'ACTIVE'),
 (9, 4, 'Jamie Wells', 'jamie.wells@example.com', 'INACTIVE'),
 (10, 5, 'Taylor Ellis', 'taylor.ellis@example.com', 'ACTIVE'),
 (11, 5, 'Cameron Lane', 'cameron.lane@example.com', 'ACTIVE'),
 (12, 1, 'Robin Hayes', 'robin.hayes@example.com', 'ACTIVE');

INSERT INTO devices (device_id, department_id, current_location_id, asset_tag, serial_number, device_type, status, purchase_date) VALUES
 (1, 1, 2, 'IT-1001', 'SYN-LT-0001', 'LAPTOP', 'ASSIGNED', '2025-01-15'),
 (2, 2, 2, 'FIN-1002', 'SYN-LT-0002', 'LAPTOP', 'ASSIGNED', '2025-02-10'),
 (3, 2, 4, 'FIN-1003', 'SYN-LT-0003', 'LAPTOP', 'ASSIGNED', '2025-02-10'),
 (4, 3, 2, 'HR-1004', 'SYN-LT-0004', 'LAPTOP', 'ASSIGNED', '2025-03-20'),
 (5, 4, 3, 'OPS-1005', 'SYN-TB-0005', 'TABLET', 'ASSIGNED', '2024-06-03'),
 (6, 4, 3, 'OPS-1006', 'SYN-PH-0006', 'PHONE', 'ASSIGNED', '2025-04-07'),
 (7, 5, 6, 'RES-1007', 'SYN-LT-0007', 'LAPTOP', 'ASSIGNED', '2025-05-12'),
 (8, 5, 6, 'RES-1008', 'SYN-DS-0008', 'DESKTOP', 'ASSIGNED', '2024-08-19'),
 (9, 1, 1, 'IT-1009', 'SYN-LT-0009', 'LAPTOP', 'AVAILABLE', '2023-09-11'),
 (10, 1, 1, 'IT-1010', 'SYN-MN-0010', 'MONITOR', 'AVAILABLE', '2025-09-01'),
 (11, 4, 5, 'OPS-1011', 'SYN-TB-0011', 'TABLET', 'MAINTENANCE', '2024-06-03'),
 (12, 2, 5, 'FIN-1012', 'SYN-LT-0012', 'LAPTOP', 'MAINTENANCE', '2023-11-15'),
 (13, 4, NULL, 'OPS-1013', 'SYN-PH-0013', 'PHONE', 'LOST', '2024-01-22'),
 (14, 3, 1, 'HR-1014', 'SYN-LT-0014', 'LAPTOP', 'RETIRED', '2020-03-09'),
 (15, 1, 1, 'IT-1015', 'SYN-LT-0015', 'LAPTOP', 'AVAILABLE', '2026-10-01'),
 (16, 5, 6, 'RES-1016', 'SYN-PR-0016', 'PRINTER', 'AVAILABLE', '2024-02-29'),
 (17, 3, 1, 'HR-1017', 'SYN-MN-0017', 'MONITOR', 'AVAILABLE', '2025-07-07'),
 (18, 4, 3, 'OPS-1018', 'SYN-TB-0018', 'TABLET', 'AVAILABLE', '2026-08-10'),
 (19, 1, 4, 'IT-1019', 'SYN-LT-0019', 'LAPTOP', 'ASSIGNED', '2026-06-15'),
 (20, 5, 6, 'RES-1020', 'SYN-MN-0020', 'MONITOR', 'AVAILABLE', NULL);

-- Older loans precede current loans, device 9 changes assigned employee, device 19 is an IT loan to finance.
INSERT INTO assignments (assignment_id, employee_id, device_id, location_id, assigned_at, due_back_at, returned_at, assignment_status, return_condition) VALUES
 (1, 9, 9, 3, '2025-09-01 09:00:00', '2026-01-31 17:00:00', '2026-01-30 15:00:00', 'CLOSED', 'GOOD'),
 (2, 6, 14, 2, '2025-01-06 09:00:00', NULL, '2026-06-01 10:00:00', 'CLOSED', 'FAIR'),
 (3, 8, 11, 3, '2026-03-02 09:00:00', '2026-10-01 17:00:00', '2026-10-01 14:00:00', 'CLOSED', 'DAMAGED'),
 (4, 4, 12, 2, '2026-02-02 09:00:00', NULL, '2026-10-15 10:00:00', 'CLOSED', 'DAMAGED'),
 (5, 3, 9, 1, '2026-02-02 09:00:00', '2026-02-20 17:00:00', '2026-02-23 10:00:00', 'CLOSED', 'GOOD'),
 (6, 7, 18, 3, '2026-09-01 08:00:00', '2026-09-15 17:00:00', '2026-09-15 16:00:00', 'CLOSED', 'GOOD'),
 (7, 1, 1, 1, '2026-01-05 09:00:00', NULL, NULL, 'OPEN', NULL),
 (8, 3, 2, 2, '2026-02-24 09:00:00', NULL, NULL, 'OPEN', NULL),
 (9, 4, 3, 1, '2026-10-16 09:00:00', '2026-11-16 17:00:00', NULL, 'OPEN', NULL),
 (10, 5, 4, 2, '2026-06-02 09:00:00', NULL, NULL, 'OPEN', NULL),
 (11, 7, 5, 3, '2026-09-16 09:00:00', '2026-10-15 17:00:00', NULL, 'OPEN', NULL),
 (12, 8, 6, 3, '2026-10-02 09:00:00', '2026-12-01 17:00:00', NULL, 'OPEN', NULL),
 (13, 10, 7, 6, '2026-08-03 09:00:00', NULL, NULL, 'OPEN', NULL),
 (14, 11, 8, 6, '2026-07-06 09:00:00', NULL, NULL, 'OPEN', NULL),
 (15, 7, 13, NULL, '2026-08-10 09:00:00', '2026-10-10 17:00:00', NULL, 'OPEN', NULL),
 (16, 4, 19, 1, '2026-10-19 09:00:00', '2026-10-26 17:00:00', NULL, 'OPEN', NULL);

INSERT INTO incidents (incident_id, device_id, reported_by_employee_id, incident_type, reported_at, details, resolved_at) VALUES
 (1, 11, 8, 'DAMAGE', '2026-10-01 11:00:00', 'Cracked screen after field inspection.', NULL),
 (2, 12, 4, 'MALFUNCTION', '2026-10-15 08:00:00', 'Battery fails to hold charge.', NULL),
 (3, 13, 7, 'LOSS', '2026-10-08 13:00:00', 'Phone missing after site visit; remote lock requested.', NULL),
 (4, 9, 3, 'MALFUNCTION', '2026-02-12 10:00:00', 'Intermittent wireless connection.', '2026-02-12 16:00:00'),
 (5, 14, 6, 'DAMAGE', '2026-05-29 14:00:00', 'Worn hinge; replacement approved.', '2026-06-02 16:00:00'),
 (6, 16, NULL, 'MALFUNCTION', '2026-09-10 08:00:00', 'Paper-feed fault detected during routine inspection.', '2026-09-10 15:00:00'),
 (7, 5, 7, 'DAMAGE', '2026-10-20 14:00:00', 'Protective case damaged; tablet remains usable.', NULL),
 (8, 11, 8, 'MALFUNCTION', '2026-09-20 09:00:00', 'Touch input intermittently unresponsive.', '2026-09-20 12:00:00');

INSERT INTO maintenance_records (maintenance_id, device_id, technician_employee_id, service_type, started_at, completed_at, notes, cost_cents) VALUES
 (1, 11, NULL, 'REPAIR', '2026-10-02 09:00:00', NULL, 'External depot awaiting replacement screen; estimate not final.', NULL),
 (2, 12, NULL, 'REPAIR', '2026-10-16 09:00:00', NULL, 'Warranty battery replacement by external vendor.', 0),
 (3, 9, 2, 'REPAIR', '2026-02-12 11:00:00', '2026-02-12 15:30:00', 'Updated wireless driver remotely.', 0),
 (4, 14, 2, 'INSPECTION', '2026-06-01 11:00:00', '2026-06-02 15:00:00', 'Uneconomical repair; sanitized and marked retired.', 2500),
 (5, 16, 1, 'PREVENTIVE', '2026-09-10 09:00:00', '2026-09-10 14:00:00', 'Cleaned rollers and replaced feed kit.', 6500),
 (6, 8, 2, 'UPGRADE', '2026-06-25 09:00:00', '2026-06-25 12:00:00', 'Installed additional memory before assignment.', 12500),
 (7, 11, 2, 'REPAIR', '2026-09-20 10:00:00', '2026-09-20 11:30:00', 'Recalibrated touch input at field office.', 0),
 (8, 15, 1, 'INSPECTION', '2026-10-02 08:00:00', '2026-10-02 09:00:00', 'New-stock acceptance test passed.', 0);

COMMIT;
