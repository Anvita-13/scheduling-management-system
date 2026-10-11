BEGIN;

CREATE TABLE alembic_version (
    version_num VARCHAR(32) NOT NULL, 
    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);

-- Running upgrade  -> 0002

CREATE TABLE registration_settings (
    id SERIAL NOT NULL, 
    phase VARCHAR(10) NOT NULL, 
    min_credits INTEGER NOT NULL, 
    max_credits INTEGER NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT ck_settings_singleton CHECK (id = 1), 
    CONSTRAINT ck_settings_credit_range CHECK (min_credits <= max_credits)
);

CREATE TABLE rooms (
    id SERIAL NOT NULL, 
    name VARCHAR(50) NOT NULL, 
    kind VARCHAR(10) NOT NULL, 
    capacity INTEGER NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT ck_room_capacity_positive CHECK (capacity > 0), 
    UNIQUE (name)
);

CREATE TABLE slots (
    id SERIAL NOT NULL, 
    name VARCHAR(40) NOT NULL, 
    kind VARCHAR(10) NOT NULL, 
    credits INTEGER NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT ck_slot_credits_positive CHECK (credits > 0), 
    UNIQUE (name)
);

CREATE TABLE subjects (
    id SERIAL NOT NULL, 
    code VARCHAR(20) NOT NULL, 
    name VARCHAR(150) NOT NULL, 
    credits INTEGER NOT NULL, 
    lab_credits INTEGER NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT ck_subjects_credits_positive CHECK (credits > 0), 
    CONSTRAINT ck_subjects_lab_credits_nonneg CHECK (lab_credits >= 0), 
    UNIQUE (code)
);

CREATE TABLE users (
    id SERIAL NOT NULL, 
    name VARCHAR(120) NOT NULL, 
    email VARCHAR(255) NOT NULL, 
    password_hash VARCHAR(255) NOT NULL, 
    role VARCHAR(10) NOT NULL, 
    is_active BOOLEAN NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id)
);

CREATE UNIQUE INDEX ix_users_email ON users (email);

CREATE INDEX ix_users_role ON users (role);

CREATE TABLE algorithm_runs (
    id SERIAL NOT NULL, 
    algorithm VARCHAR(50) NOT NULL, 
    status VARCHAR(20) NOT NULL, 
    summary JSON NOT NULL, 
    triggered_by INTEGER, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(triggered_by) REFERENCES users (id) ON DELETE SET NULL
);

CREATE INDEX ix_algorithm_runs_algorithm ON algorithm_runs (algorithm);

CREATE TABLE curriculum (
    id SERIAL NOT NULL, 
    group_code VARCHAR(20) NOT NULL, 
    subject_id INTEGER NOT NULL, 
    is_mandatory BOOLEAN NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(subject_id) REFERENCES subjects (id) ON DELETE CASCADE, 
    CONSTRAINT uq_curriculum_group_subject UNIQUE (group_code, subject_id)
);

CREATE INDEX ix_curriculum_group_code ON curriculum (group_code);

CREATE TABLE faculty (
    user_id INTEGER NOT NULL, 
    employee_code VARCHAR(30) NOT NULL, 
    department VARCHAR(100) NOT NULL, 
    PRIMARY KEY (user_id), 
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
    UNIQUE (employee_code)
);

CREATE TABLE notifications (
    id SERIAL NOT NULL, 
    user_id INTEGER NOT NULL, 
    type VARCHAR(30) NOT NULL, 
    message TEXT NOT NULL, 
    is_read BOOLEAN NOT NULL, 
    dedupe_key VARCHAR(120), 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE INDEX ix_notif_user_read ON notifications (user_id, is_read, created_at);

CREATE INDEX ix_notifications_dedupe_key ON notifications (dedupe_key);

CREATE TABLE slot_periods (
    id SERIAL NOT NULL, 
    slot_id INTEGER NOT NULL, 
    day VARCHAR(3) NOT NULL, 
    start_time TIME WITHOUT TIME ZONE NOT NULL, 
    end_time TIME WITHOUT TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT ck_slot_period_start_before_end CHECK (start_time < end_time), 
    FOREIGN KEY(slot_id) REFERENCES slots (id) ON DELETE CASCADE, 
    CONSTRAINT uq_slot_period UNIQUE (slot_id, day, start_time)
);

CREATE INDEX ix_slot_periods_slot ON slot_periods (slot_id);

CREATE TABLE students (
    user_id INTEGER NOT NULL, 
    roll_number VARCHAR(30) NOT NULL, 
    max_credits INTEGER NOT NULL, 
    selected_credits INTEGER, 
    group_code VARCHAR(20), 
    PRIMARY KEY (user_id), 
    CONSTRAINT ck_students_max_credits_positive CHECK (max_credits > 0), 
    CONSTRAINT ck_students_selected_credits CHECK (selected_credits IS NULL OR selected_credits > 0), 
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
    UNIQUE (roll_number)
);

CREATE INDEX ix_students_group_code ON students (group_code);

CREATE TABLE faculty_subjects (
    faculty_id INTEGER NOT NULL, 
    subject_id INTEGER NOT NULL, 
    default_capacity INTEGER NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (faculty_id, subject_id), 
    CONSTRAINT ck_fs_default_capacity CHECK (default_capacity >= 0), 
    FOREIGN KEY(faculty_id) REFERENCES faculty (user_id) ON DELETE CASCADE, 
    FOREIGN KEY(subject_id) REFERENCES subjects (id) ON DELETE CASCADE
);

CREATE TABLE class_sections (
    id SERIAL NOT NULL, 
    subject_id INTEGER NOT NULL, 
    faculty_id INTEGER NOT NULL, 
    capacity INTEGER NOT NULL, 
    enrolled_count INTEGER NOT NULL, 
    status VARCHAR(10) NOT NULL, 
    next_queue_seq INTEGER NOT NULL, 
    theory_slot_id INTEGER, 
    lab_slot_id INTEGER, 
    room_id INTEGER, 
    lab_room_id INTEGER, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    CONSTRAINT ck_class_capacity_nonneg CHECK (capacity >= 0), 
    CONSTRAINT ck_class_enrolled_le_capacity CHECK (enrolled_count <= capacity), 
    CONSTRAINT ck_class_enrolled_nonneg CHECK (enrolled_count >= 0), 
    CONSTRAINT fk_class_faculty_subject FOREIGN KEY(faculty_id, subject_id) REFERENCES faculty_subjects (faculty_id, subject_id) ON DELETE CASCADE, 
    FOREIGN KEY(faculty_id) REFERENCES faculty (user_id) ON DELETE CASCADE, 
    FOREIGN KEY(lab_room_id) REFERENCES rooms (id) ON DELETE SET NULL, 
    FOREIGN KEY(lab_slot_id) REFERENCES slots (id) ON DELETE SET NULL, 
    FOREIGN KEY(room_id) REFERENCES rooms (id) ON DELETE SET NULL, 
    FOREIGN KEY(subject_id) REFERENCES subjects (id) ON DELETE CASCADE, 
    FOREIGN KEY(theory_slot_id) REFERENCES slots (id) ON DELETE SET NULL, 
    CONSTRAINT uq_class_subject_faculty UNIQUE (subject_id, faculty_id)
);

CREATE INDEX ix_class_sections_faculty_id ON class_sections (faculty_id);

CREATE INDEX ix_class_subject_status ON class_sections (subject_id, status);

CREATE TABLE join_requests (
    id SERIAL NOT NULL, 
    student_id INTEGER NOT NULL, 
    class_id INTEGER NOT NULL, 
    subject_id INTEGER NOT NULL, 
    queue_seq INTEGER, 
    requested_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    status VARCHAR(10) NOT NULL, 
    decision_reason VARCHAR(200), 
    decided_at TIMESTAMP WITH TIME ZONE, 
    PRIMARY KEY (id), 
    FOREIGN KEY(class_id) REFERENCES class_sections (id) ON DELETE CASCADE, 
    FOREIGN KEY(student_id) REFERENCES students (user_id) ON DELETE CASCADE, 
    FOREIGN KEY(subject_id) REFERENCES subjects (id) ON DELETE CASCADE, 
    CONSTRAINT uq_request_class_seq UNIQUE (class_id, queue_seq)
);

CREATE INDEX ix_join_requests_student_id ON join_requests (student_id);

CREATE INDEX ix_request_queue ON join_requests (class_id, status, queue_seq);

CREATE UNIQUE INDEX uq_request_student_subject_active ON join_requests (student_id, subject_id) WHERE status IN ('PENDING', 'ACCEPTED');

CREATE TABLE registrations (
    id SERIAL NOT NULL, 
    student_id INTEGER NOT NULL, 
    subject_id INTEGER NOT NULL, 
    class_id INTEGER, 
    status VARCHAR(10) NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(class_id) REFERENCES class_sections (id) ON DELETE SET NULL, 
    FOREIGN KEY(student_id) REFERENCES students (user_id) ON DELETE CASCADE, 
    FOREIGN KEY(subject_id) REFERENCES subjects (id) ON DELETE CASCADE, 
    CONSTRAINT uq_registration_student_subject UNIQUE (student_id, subject_id)
);

CREATE INDEX ix_registrations_class_id ON registrations (class_id);

CREATE INDEX ix_registrations_student_id ON registrations (student_id);

CREATE INDEX ix_registrations_subject_id ON registrations (subject_id);

INSERT INTO alembic_version (version_num) VALUES ('0002') RETURNING alembic_version.version_num;

COMMIT;

