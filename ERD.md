# Final entity–relationship diagram

This diagram matches `schema.sql`. GitHub renders the Mermaid block below. `PK`, `FK`, and `UK` denote primary, foreign, and unique keys. Required attributes are NOT NULL; optional attributes allow NULL. Integer primary keys identify each record and are assigned automatically when omitted.

```mermaid
erDiagram
    departments ||--o{ employees : organizes
    departments ||--o{ devices : owns
    locations |o--o{ devices : expected_location
    employees ||--o{ assignments : holds_over_time
    devices ||--o{ assignments : custody_history
    locations |o--o{ assignments : issued_at
    devices ||--o{ incidents : has
    employees |o--o{ incidents : reports
    devices ||--o{ maintenance_records : service_history
    employees |o--o{ maintenance_records : performs
    departments {
        INTEGER department_id PK
        TEXT department_name UK "required"
        TEXT manager_name "optional"
    }
    locations {
        INTEGER location_id PK
        TEXT location_name "required"
        TEXT address "optional"
        TEXT location_type "optional"
    }
    employees {
        INTEGER employee_id PK
        INTEGER department_id FK "required"
        TEXT full_name "required"
        TEXT email UK "required; case-insensitive"
        TEXT employment_status "required; default ACTIVE"
    }
    devices {
        INTEGER device_id PK
        INTEGER department_id FK "required"
        INTEGER current_location_id FK "optional"
        TEXT asset_tag UK "required"
        TEXT serial_number UK "required"
        TEXT device_type "required"
        TEXT status "required; default AVAILABLE"
        TEXT purchase_date "optional; YYYY-MM-DD"
    }
    assignments {
        INTEGER assignment_id PK
        INTEGER employee_id FK "required"
        INTEGER device_id FK "required"
        INTEGER location_id FK "optional"
        TEXT assigned_at "required; UTC timestamp"
        TEXT due_back_at "optional; UTC timestamp"
        TEXT returned_at "optional; UTC timestamp"
        TEXT assignment_status "required; default OPEN"
        TEXT return_condition "optional"
    }
    incidents {
        INTEGER incident_id PK
        INTEGER device_id FK "required"
        INTEGER reported_by_employee_id FK "optional"
        TEXT incident_type "required"
        TEXT reported_at "required; UTC timestamp"
        TEXT details "optional"
        TEXT resolved_at "optional; UTC timestamp"
    }
    maintenance_records {
        INTEGER maintenance_id PK
        INTEGER device_id FK "required"
        INTEGER technician_employee_id FK "optional"
        TEXT service_type "required"
        TEXT started_at "required; UTC timestamp"
        TEXT completed_at "optional; UTC timestamp"
        TEXT notes "optional"
        INTEGER cost_cents "optional; nonnegative"
    }
```

Each department can have zero or more employees/devices. Every assignment requires a device and employee; an issue location may be unknown. Expected locations, incident reporters, and maintenance technicians can also be unknown. Referenced records cannot be deleted while dependent records exist (`ON DELETE RESTRICT`).

Assignments resolve the employee/device many-to-many relationship over time. A partial unique index permits only one OPEN assignment per device. Triggers reject overlapping custody intervals. These temporal rules supplement the diagram's cardinalities.

The earlier PNG contained the same entities and columns but omitted the required employment status and showed mandatory relationships for some nullable locations/reporters/technicians. This final diagram corrects those annotations to match the existing SQL. The database itself was not changed. Allowed codes, chronological checks, and the accountability view are defined in full in `schema.sql`.
