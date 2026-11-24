-- Run after schema.sql and insert_data.sql, use SQLite 3.37+
-- Report cutoff: 2026-11-02 00:00:00 UTC
PRAGMA foreign_keys = ON;

-- Requirement 1: Filtering and Sorting
-- Which devices are available for assignment? List laptops and other
-- available equipment by type and asset tag so IT doesn't accidentally
-- assign an unavailable device.
SELECT asset_tag, device_type, status, purchase_date
FROM devices
WHERE status = 'AVAILABLE'
ORDER BY device_type, asset_tag;

-- Requirement 2: INNER JOIN
-- Which devices have been reported lost, stolen, or damaged?
-- Include resolved incidents so this is like a historical incident report.
SELECT d.asset_tag, d.device_type, i.incident_id, i.incident_type,
       i.reported_at, i.resolved_at, i.details
FROM incidents AS i
INNER JOIN devices AS d ON d.device_id = i.device_id
WHERE i.incident_type IN ('LOSS', 'THEFT', 'DAMAGE')
ORDER BY i.reported_at DESC, i.incident_id;

-- Requirement 3: LEFT JOIN
-- Which departments own the most devices? Include departments with
-- no equipment: New Ventures must appear with a zero.
-- COUNT(device_id), rather than COUNT(*).
-- Counts only actual matched devices.
SELECT dep.department_name, COUNT(d.device_id) AS owned_device_count
FROM departments AS dep
LEFT JOIN devices AS d ON d.department_id = dep.department_id
GROUP BY dep.department_id, dep.department_name
ORDER BY owned_device_count DESC, dep.department_name;

-- Requirement 4: Three-Table Join
-- What is the full assignment history of a particular device?
-- Follow device IT-1009 through all of its previous assignments and issue
-- locations. The device/date assignment index supports the lookup.
SELECT d.asset_tag, a.assignment_id, e.full_name AS custodian_name,
       loc.location_name AS issued_at_location, a.assigned_at,
       a.due_back_at, a.returned_at, a.assignment_status, a.return_condition
FROM devices AS d
INNER JOIN assignments AS a ON a.device_id = d.device_id
INNER JOIN employees AS e ON e.employee_id = a.employee_id
LEFT JOIN locations AS loc ON loc.location_id = a.location_id
WHERE d.asset_tag = 'IT-1009'
ORDER BY a.assigned_at, a.assignment_id;

-- Requirement 5: Aggregate Query
-- How much recorded service work and cost does IT manage?
-- NULL costs are unknown, not free, so their count has to be
-- reported separately. Known costs include any recorded
-- estimates for unfinished work as well as invoices.
SELECT COUNT(*) AS service_record_count,
       COUNT(DISTINCT device_id) AS serviced_device_count,
       SUM(CASE WHEN completed_at IS NULL THEN 1 ELSE 0 END) AS unfinished_services,
       COUNT(cost_cents) AS records_with_known_cost,
       COUNT(*) - COUNT(cost_cents) AS records_with_unknown_cost,
       ROUND(SUM(cost_cents) / 100.0, 2) AS total_known_cost_dollars,
       ROUND(AVG(cost_cents) / 100.0, 2) AS average_known_cost_dollars
FROM maintenance_records;

-- Requirement 6: GROUP BY and HAVING
-- Which devices have repeated incidents and should be investigated?
-- Group all incident history, but only show devices with at least two incidents.
SELECT d.asset_tag, COUNT(i.incident_id) AS incident_count,
       MIN(i.reported_at) AS first_reported_at,
       MAX(i.reported_at) AS latest_reported_at
FROM devices AS d
INNER JOIN incidents AS i ON i.device_id = d.device_id
GROUP BY d.device_id, d.asset_tag
HAVING COUNT(i.incident_id) >= 2
ORDER BY incident_count DESC, d.asset_tag;

-- Requirement 7: Subquery
-- Which employees currently have overdue, unreturned equipment?
-- Returns each employee once even if they have multiple overdue loans.
-- An open loan with no due date is not automatically flagged as overdue.
SELECT e.employee_id, e.full_name, e.email, e.employment_status
FROM employees AS e
WHERE EXISTS (
    SELECT 1
    FROM assignments AS a
    WHERE a.employee_id = e.employee_id
      AND a.assignment_status = 'OPEN'
      AND a.due_back_at < '2026-11-02 00:00:00'
)
ORDER BY e.full_name, e.employee_id;

-- Requirement 8: Set Operation
-- Which assets need follow-up because of an unresolved incident
-- or unfinished service? UNION removes overlap so an asset with
-- both problems only appears once in the list.
SELECT d.device_id, d.asset_tag, d.device_type
FROM devices AS d
INNER JOIN incidents AS i ON i.device_id = d.device_id
WHERE i.resolved_at IS NULL
UNION
SELECT d.device_id, d.asset_tag, d.device_type
FROM devices AS d
INNER JOIN maintenance_records AS m ON m.device_id = d.device_id
WHERE m.completed_at IS NULL
ORDER BY asset_tag;

-- Requirement 9: View
-- Where should a problem device be, and who is responsible for it?
-- Use v_device_accountability to combine custody, location, department, and pending
-- issues without duplicating its joins. Include overdue loans.
SELECT asset_tag, status, owning_department,
       COALESCE(expected_location, 'Unknown location') AS expected_location,
       COALESCE(custodian_name, 'No current custodian') AS current_custodian,
       due_back_at, unresolved_incidents, open_service_records,
       CASE WHEN due_back_at < '2026-11-02 00:00:00' THEN 'YES'
            ELSE 'NO' END AS overdue_at_report_cutoff
FROM v_device_accountability
WHERE unresolved_incidents > 0
   OR open_service_records > 0
   OR due_back_at < '2026-11-02 00:00:00'
ORDER BY asset_tag;
