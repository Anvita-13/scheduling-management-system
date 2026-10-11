import { Navigate, Route, Routes } from 'react-router-dom'
import { ROLE_HOME, useAuth } from './auth/AuthContext'
import ProtectedRoute from './auth/ProtectedRoute'
import DashboardLayout from './layouts/DashboardLayout'
import Login from './pages/Login'
import NotificationsPage from './pages/shared/NotificationsPage'
import TimetablePage from './pages/shared/TimetablePage'

import AdminDashboard from './pages/admin/Dashboard'
import AdminOfferings from './pages/admin/Offerings'
import AdminSlotChart from './pages/admin/SlotChart'
import AdminScheduling from './pages/admin/Scheduling'
import AdminRegistration from './pages/admin/Registration'
import AdminDemand from './pages/admin/Demand'
import AdminInsights from './pages/admin/Insights'
import AdminPeople from './pages/admin/People'

import FacultyDashboard from './pages/faculty/Dashboard'
import FacultyClasses from './pages/faculty/Classes'
import FacultyClassDetail from './pages/faculty/ClassDetail'

import StudentDashboard from './pages/student/Dashboard'
import StudentCredits from './pages/student/Credits'
import StudentSubjects from './pages/student/Subjects'
import StudentSubjectClasses from './pages/student/SubjectClasses'
import StudentRequests from './pages/student/Requests'
import StudentSlotView from './pages/student/SlotView'

function Home() {
  const { user } = useAuth()
  return <Navigate to={user ? ROLE_HOME[user.role] : '/login'} replace />
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/" element={<Home />} />

      <Route path="/admin" element={<ProtectedRoute role="ADMIN" />}>
        <Route element={<DashboardLayout />}>
          <Route index element={<AdminDashboard />} />
          <Route path="offerings" element={<AdminOfferings />} />
          <Route path="slot-chart" element={<AdminSlotChart />} />
          <Route path="scheduling" element={<AdminScheduling />} />
          <Route path="registration" element={<AdminRegistration />} />
          <Route path="demand" element={<AdminDemand />} />
          <Route path="insights" element={<AdminInsights />} />
          <Route path="people" element={<AdminPeople />} />
          <Route path="notifications" element={<NotificationsPage />} />
        </Route>
      </Route>

      <Route path="/faculty" element={<ProtectedRoute role="FACULTY" />}>
        <Route element={<DashboardLayout />}>
          <Route index element={<FacultyDashboard />} />
          <Route path="classes" element={<FacultyClasses />} />
          <Route path="classes/:classId" element={<FacultyClassDetail />} />
          <Route path="timetable" element={<TimetablePage title="My teaching timetable" />} />
          <Route path="notifications" element={<NotificationsPage />} />
        </Route>
      </Route>

      <Route path="/student" element={<ProtectedRoute role="STUDENT" />}>
        <Route element={<DashboardLayout />}>
          <Route index element={<StudentDashboard />} />
          <Route path="credits" element={<StudentCredits />} />
          <Route path="subjects" element={<StudentSubjects />} />
          <Route path="subjects/:subjectId" element={<StudentSubjectClasses />} />
          <Route path="slots" element={<StudentSlotView />} />
          <Route path="requests" element={<StudentRequests />} />
          <Route path="timetable" element={<TimetablePage title="My timetable" />} />
          <Route path="notifications" element={<NotificationsPage />} />
        </Route>
      </Route>

      <Route path="*" element={<Home />} />
    </Routes>
  )
}
