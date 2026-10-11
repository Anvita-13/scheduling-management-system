// Every backend endpoint the UI uses, grouped by role. Pages never build URLs themselves.
import { del, get, patch, post, put } from './client'

export const authApi = {
  login: (email, password) => post('/auth/login', { email, password }),
  me: () => get('/auth/me'),
}

export const notificationApi = {
  list: (unreadOnly = false) => get('/notifications', { unread_only: unreadOnly || null }),
  unreadCount: () => get('/notifications/unread-count'),
  markRead: (id) => post(`/notifications/${id}/read`),
  markAllRead: () => post('/notifications/read-all'),
}

export const timetableApi = {
  mine: () => get('/timetable'),
}

export const studentApi = {
  profile: () => get('/student/profile'),
  setCredits: (credits) => put('/student/credits', { credits }),
  subjects: () => get('/student/subjects'),
  selectSubject: (id) => post(`/student/subjects/${id}/select`),
  dropSubject: (id) => del(`/student/subjects/${id}/select`),
  classOptions: (subjectId) => get(`/student/subjects/${subjectId}/classes`),
  offerings: () => get('/student/offerings'),
  requestClass: (classId) => post('/student/requests', { class_id: classId }),
  requests: () => get('/student/requests'),
  cancelRequest: (id) => del(`/student/requests/${id}`),
}

export const facultyApi = {
  dashboard: () => get('/faculty/dashboard'),
  classes: () => get('/faculty/classes'),
  classDetail: (id) => get(`/faculty/classes/${id}`),
  acceptNext: (classId, requestId) => post(`/faculty/classes/${classId}/accept-next`, {}, { request_id: requestId }),
  rejectNext: (classId, requestId) => post(`/faculty/classes/${classId}/reject-next`, {}, { request_id: requestId }),
  closeClass: (classId) => post(`/faculty/classes/${classId}/close`),
}

export const adminApi = {
  dashboard: () => get('/admin/dashboard'),
  faculty: () => get('/admin/faculty'),
  createFaculty: (b) => post('/admin/faculty', b),
  students: () => get('/admin/students'),
  createStudent: (b) => post('/admin/students', b),
  curriculum: () => get('/admin/curriculum'),
  // subjects and offerings (a faculty member + their slots)
  subjects: () => get('/admin/subjects'),
  createSubject: (b) => post('/admin/subjects', b),
  deleteSubject: (id) => del(`/admin/subjects/${id}`),
  slots: (params) => get('/admin/slots', params),
  loadStandardSlots: () => post('/admin/slots/load-standard'),
  eligibleFaculty: (params) => get('/admin/eligible-faculty', params),
  createOffering: (b) => post('/admin/offerings', b),
  placeOffering: (classId, b) => patch(`/admin/offerings/${classId}/slots`, b),
  deleteOffering: (classId) => del(`/admin/offerings/${classId}`),
  // seats / status
  classes: () => get('/admin/classes'),
  setCapacity: (id, capacity) => patch(`/admin/classes/${id}/capacity`, { capacity }),
  closeClass: (id) => post(`/admin/classes/${id}/close`),
  reopenClass: (id) => post(`/admin/classes/${id}/reopen`),
  registration: () => get('/admin/registration'),
  updateRegistration: (b) => put('/admin/registration', b),
  demand: () => get('/admin/demand'),
  // rooms (type + size only; assignment is automatic)
  rooms: () => get('/admin/rooms'),
  createRoom: (b) => post('/admin/rooms', b),
  deleteRoom: (id) => del(`/admin/rooms/${id}`),
  // scheduling optimisation
  slotChart: () => get('/admin/slot-chart'),
  clashes: () => get('/admin/scheduling/clashes'),
  autoAssign: () => post('/admin/scheduling/auto-assign'),
  assignRooms: () => post('/admin/scheduling/assign-rooms'),
  clearPlacements: () => post('/admin/scheduling/clear'),
  // algorithm insights (read-only)
  insightFifo: (classId) => get(`/admin/insights/fifo/${classId}`),
  insightGreedy: (params) => get('/admin/insights/greedy', params),
  insightColoring: () => get('/admin/insights/graph-coloring'),
  insightMaxFlow: () => get('/admin/insights/max-flow'),
  runMaxFlow: () => post('/admin/insights/max-flow/run'),
  algorithmRuns: () => get('/admin/algorithm-runs'),
}
