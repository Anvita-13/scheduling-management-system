import enum


class Role(str, enum.Enum):
    ADMIN = "ADMIN"
    FACULTY = "FACULTY"
    STUDENT = "STUDENT"


class ClassStatus(str, enum.Enum):
    OPEN = "OPEN"      # accepting requests
    FULL = "FULL"      # closed automatically because every seat is taken
    CLOSED = "CLOSED"  # closed manually (faculty/admin)


class RequestStatus(str, enum.Enum):
    PENDING = "PENDING"      # sitting in the class's FIFO queue
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"    # class full/closed, or declined by faculty
    CANCELLED = "CANCELLED"  # withdrawn by the student


class RegistrationStatus(str, enum.Enum):
    SELECTED = "SELECTED"    # student picked the subject, no active request / seat
    REQUESTED = "REQUESTED"  # a join request is waiting in a queue
    ENROLLED = "ENROLLED"    # seat confirmed


class RegistrationPhase(str, enum.Enum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"


class SlotKind(str, enum.Enum):
    THEORY = "THEORY"
    LAB = "LAB"


class RoomKind(str, enum.Enum):
    LECTURE = "LECTURE"
    LAB = "LAB"


class NotificationType(str, enum.Enum):
    CLASS_FULL = "CLASS_FULL"
    REQUEST_ACCEPTED = "REQUEST_ACCEPTED"
    REQUEST_REJECTED = "REQUEST_REJECTED"
    NEW_JOIN_REQUEST = "NEW_JOIN_REQUEST"
    NO_FACULTY_AVAILABLE = "NO_FACULTY_AVAILABLE"
    CLASS_CLOSED = "CLASS_CLOSED"
    CAPACITY_INCREASED = "CAPACITY_INCREASED"
    TIMETABLE_GENERATED = "TIMETABLE_GENERATED"
    SCHEDULE_UPDATED = "SCHEDULE_UPDATED"
    REGISTRATION_STATUS = "REGISTRATION_STATUS"
    REOPEN_REQUESTED = "REOPEN_REQUESTED"
    REOPEN_DECLINED = "REOPEN_DECLINED"
    CLASS_REOPENED = "CLASS_REOPENED"
    INFO = "INFO"


RejectionReason = str
REASON_CLASS_FULL = "CLASS_FULL"
REASON_CLASS_CLOSED = "CLASS_CLOSED"
REASON_FACULTY_DECLINED = "FACULTY_DECLINED"

DAY_ORDER = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
