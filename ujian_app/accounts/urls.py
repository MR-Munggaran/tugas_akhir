from django.urls import path
from . import views

urlpatterns = [
    path('register/guru/', views.register_guru, name='register_guru'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('edit-profile/', views.edit_profile, name='edit_profile'),

    # Student Management
    path('students/', views.student_list, name='student_list'),  # Pastikan ini ada
    path('students/create/', views.student_create, name='student_create'),
    path('students/update/<int:pk>/', views.student_update, name='student_update'),
    path('students/delete/<int:pk>/', views.student_delete, name='student_delete'),
    path('face-verification/', views.face_verification, name='face_verification'),

    # Kelas Management
    path('kelas/', views.kelas_list, name='kelas_list'),
    path('kelas/create/', views.kelas_create, name='kelas_create'),
    path('kelas/update/<int:pk>/', views.kelas_update, name='kelas_update'),
    path('kelas/delete/<int:pk>/', views.kelas_delete, name='kelas_delete'),

    # Log Masuk Student
    path('logs/', views.log_masuk_student, name='log_masuk_student'),

    # Ujian Management
    path('ujian/', views.ujian_list, name='ujian_list'),
    path('ujian/create/', views.ujian_create, name='ujian_create'),
    path('ujian/update/<int:pk>/', views.ujian_update, name='ujian_update'),
    path('ujian/delete/<int:pk>/', views.ujian_delete, name='ujian_delete'),
    path('proctoring-check/', views.proctoring_check, name='proctoring_check'),

    # Soal Management
    path('ujian/<int:ujian_id>/soal/', views.soal_list, name='soal_list'),
    path('ujian/<int:ujian_id>/soal/create/', views.soal_create, name='soal_create'),
    path('soal/update/<int:soal_id>/', views.soal_update, name='soal_update'),
    path('soal/delete/<int:soal_id>/', views.soal_delete, name='soal_delete'),

    # Akses Ujian oleh Siswa
    path('ujian/akses/', views.akses_ujian, name='akses_ujian'),

    path('ujian/<int:ujian_id>/kerjakan/', views.kerjakan_ujian, name='kerjakan_ujian'),
    path('nilai/', views.nilai_siswa, name='nilai_siswa'),
    path('nilai/<int:ujian_id>/', views.nilai_guru, name='nilai_guru'),
    path('nilai/<int:ujian_id>/detail/', views.nilai_detail, name='nilai_detail'),

    path('student/<int:student_id>/voice-upload/', views.voice_upload, name='voice_upload'),
    path('voice-verification/', views.voice_verification, name='voice_verification'),
    path('delete_voice_samples/<int:student_id>/', views.delete_voice_samples, name='delete_voice_samples'),
    path('enroll-face/<int:pk>/', views.enroll_face, name='enroll_face'),
    path('face-delete/<int:pk>/', views.delete_face, name='delete_face'),

    path('face-test/<int:pk>/', views.test_face, name='face_test'),
    path('face-evaluation/', views.face_evaluation_view, name='face_evaluation'),
    path('voice-evaluation/', views.voice_evaluation_view, name='voice_evaluation'),
]