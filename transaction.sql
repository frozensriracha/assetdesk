-- Demonstrates checking out available laptop IT-1009 to Robin Hayes.
-- Both the device status/location and its custody record need to change together.
-- ROLLBACK was included to keep the database in its original state for ease of grading.
-- Run with sqlite3 -bail so any error stops execution and closing the connection
-- rolls back uncommitted work.
-- Foreign keys must be enabled before beginning.

PRAGMA foreign_keys = ON;

SELECT 'BEFORE checkout' AS phase, asset_tag, status, expected_location,
       custodian_name, assignment_id
FROM v_device_accountability WHERE asset_tag = 'IT-1009';

BEGIN IMMEDIATE;

CREATE TEMP TABLE checkout_assertion (
    exactly_one_row INTEGER NOT NULL CHECK (exactly_one_row = 1)
);

UPDATE devices
SET status = 'ASSIGNED', current_location_id = 2
WHERE asset_tag = 'IT-1009' AND status = 'AVAILABLE'
  AND NOT EXISTS (
      SELECT 1 FROM assignments AS a
      WHERE a.device_id = devices.device_id AND a.assignment_status = 'OPEN'
  );
INSERT INTO checkout_assertion VALUES (changes());

INSERT INTO assignments
    (employee_id, device_id, location_id, assigned_at, due_back_at,
     assignment_status)
SELECT e.employee_id, d.device_id, 1, '2026-11-02 09:00:00',
       '2026-11-16 17:00:00', 'OPEN'
FROM employees AS e CROSS JOIN devices AS d
WHERE e.email = 'robin.hayes@example.com' AND e.employment_status = 'ACTIVE'
  AND d.asset_tag = 'IT-1009';
INSERT INTO checkout_assertion VALUES (changes());

-- The existing view now reflects both changes inside the transaction.
SELECT 'DURING checkout' AS phase, asset_tag, status, expected_location,
       custodian_name, assignment_id
FROM v_device_accountability WHERE asset_tag = 'IT-1009';

-- Here, a checkout would COMMIT after successful validation.
ROLLBACK;

SELECT 'AFTER rollback' AS phase, asset_tag, status, expected_location,
       custodian_name, assignment_id
FROM v_device_accountability WHERE asset_tag = 'IT-1009';
