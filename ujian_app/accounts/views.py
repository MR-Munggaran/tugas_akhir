from django.utils import timezone
from datetime import datetime, timedelta
from django.utils.timezone import make_aware
import pytz
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from .forms import GuruRegistrationForm, SiswaCreationForm, SiswaForm, KelasForm, UjianForm, SoalForm
from .models import Siswa, Kelas, LogMasukStudent, User, Ujian, Soal, HasilUjian

# Cek apakah user adalah guru atau admin
def is_guru_or_admin(user):
    return user.is_authenticated and (user.is_guru or user.is_superuser)

# Register Guru
def register_guru(request):
    if request.method == 'POST':
        form = GuruRegistrationForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('login')
    else:
        form = GuruRegistrationForm()
    return render(request, 'accounts/register_guru.html', {'form': form})

# Login
def login_view(request):
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect('dashboard')
        else:
            return render(request, 'accounts/login.html', {'error': 'Username atau password salah'})
    return render(request, 'accounts/login.html')

# Logout
@login_required
def logout_view(request):
    logout(request)
    return redirect('login')

# Dashboard
@login_required
def dashboard(request):
    return render(request, 'accounts/dashboard.html')

# Student List
@login_required
@user_passes_test(is_guru_or_admin)
def student_list(request):
    students = Siswa.objects.all()
    return render(request, 'students/student_list.html', {'students': students})

# Create Student (Hanya bisa diakses oleh Guru atau Admin)
@login_required
@user_passes_test(is_guru_or_admin)
def student_create(request):
    if request.method == 'POST':
        form = SiswaCreationForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('student_list')
        else:
            # Debug: Cetak error form jika form tidak valid
            print(form.errors)  # Tambahkan ini untuk melihat error
    else:
        form = SiswaCreationForm()
    return render(request, 'students/student_form.html', {'form': form})

# Update Student (Hanya bisa diakses oleh Guru atau Admin)
@login_required
@user_passes_test(is_guru_or_admin)
def student_update(request, pk):
    student = get_object_or_404(Siswa, pk=pk)
    if request.method == 'POST':
        form = SiswaForm(request.POST, instance=student)
        if form.is_valid():
            form.save()
            return redirect('student_list')
    else:
        form = SiswaForm(instance=student)
    return render(request, 'students/student_form.html', {'form': form})

# Delete Student (Hanya bisa diakses oleh Guru atau Admin)
@login_required
@user_passes_test(is_guru_or_admin)
def student_delete(request, pk):
    student = get_object_or_404(Siswa, pk=pk)
    if request.method == 'POST':
        student.delete()
        return redirect('student_list')
    return render(request, 'students/student_confirm_delete.html', {'student': student})

# Kelas List
@login_required
@user_passes_test(is_guru_or_admin)
def kelas_list(request):
    kelas = Kelas.objects.all()
    return render(request, 'students/kelas_list.html', {'kelas': kelas})

# Kelas Create (Hanya bisa diakses oleh Guru atau Admin)
@login_required
@user_passes_test(is_guru_or_admin)
def kelas_create(request):
    if request.method == 'POST':
        form = KelasForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('kelas_list')
    else:
        form = KelasForm()
    return render(request, 'students/kelas_form.html', {'form': form})

# Kelas Update (Hanya bisa diakses oleh Guru atau Admin)
@login_required
@user_passes_test(is_guru_or_admin)
def kelas_update(request, pk):
    kelas = get_object_or_404(Kelas, pk=pk)
    if request.method == 'POST':
        form = KelasForm(request.POST, instance=kelas)
        if form.is_valid():
            form.save()
            return redirect('kelas_list')
    else:
        form = KelasForm(instance=kelas)
    return render(request, 'students/kelas_form.html', {'form': form})

# Kelas Delete (Hanya bisa diakses oleh Guru atau Admin)
@login_required
@user_passes_test(is_guru_or_admin)
def kelas_delete(request, pk):
    kelas = get_object_or_404(Kelas, pk=pk)
    if request.method == 'POST':
        kelas.delete()
        return redirect('kelas_list')
    return render(request, 'students/kelas_confirm_delete.html', {'kelas': kelas})

# Log Masuk Student
@login_required
@user_passes_test(is_guru_or_admin)
def log_masuk_student(request):
    logs = LogMasukStudent.objects.all().order_by('-waktu_masuk')
    return render(request, 'students/log_masuk_student.html', {'logs': logs})

# List Ujian
@login_required
def ujian_list(request):
    ujian = Ujian.objects.filter(guru=request.user)  # Hanya menampilkan ujian yang dibuat oleh guru yang login
    return render(request, 'exams/ujian_list.html', {'ujian': ujian})

# Create Ujian
@login_required
def ujian_create(request):
    if request.method == 'POST':
        form = UjianForm(request.POST)
        if form.is_valid():
            ujian = form.save(commit=False)
            ujian.guru = request.user
            
            # Hapus dua baris ini
            # local_tz = pytz.timezone('Asia/Jakarta')
            # ujian.waktu_mulai = make_aware(ujian.waktu_mulai, local_tz)
            # ujian.waktu_selesai = make_aware(ujian.waktu_selesai, local_tz)
            
            ujian.save()
            return redirect('ujian_list')
        else:
            return render(request, 'exams/ujian_form.html', {'form': form})
    else:
        form = UjianForm()
    return render(request, 'exams/ujian_form.html', {'form': form})

# Update Ujian
@login_required
def ujian_update(request, pk):
    ujian = get_object_or_404(Ujian, pk=pk, guru=request.user)  # Hanya guru yang membuat ujian bisa mengedit
    if request.method == 'POST':
        form = UjianForm(request.POST, instance=ujian)
        if form.is_valid():
            form.save()
            return redirect('ujian_list')
    else:
        form = UjianForm(instance=ujian)
    return render(request, 'exams/ujian_form.html', {'form': form})

# Delete Ujian
@login_required
def ujian_delete(request, pk):
    ujian = get_object_or_404(Ujian, pk=pk, guru=request.user)  # Hanya guru yang membuat ujian bisa menghapus
    if request.method == 'POST':
        ujian.delete()
        return redirect('ujian_list')
    return render(request, 'exams/ujian_confirm_delete.html', {'ujian': ujian})

# List Soal untuk Ujian Tertentu
@login_required
def soal_list(request, ujian_id):
    ujian = get_object_or_404(Ujian, pk=ujian_id, guru=request.user)  # Hanya guru yang membuat ujian bisa melihat soal
    soal = Soal.objects.filter(ujian=ujian)
    return render(request, 'exams/soal_list.html', {'ujian': ujian, 'soal': soal})

# Create Soal
@login_required
def soal_create(request, ujian_id):
    ujian = get_object_or_404(Ujian, pk=ujian_id, guru=request.user)  # Hanya guru yang membuat ujian bisa menambah soal
    if request.method == 'POST':
        form = SoalForm(request.POST)
        if form.is_valid():
            soal = form.save(commit=False)
            soal.ujian = ujian
            soal.save()
            return redirect('soal_list', ujian_id=ujian.id)
    else:
        form = SoalForm()
    return render(request, 'exams/soal_form.html', {'form': form, 'ujian': ujian})

# Update Soal
@login_required
def soal_update(request, soal_id):
    soal = get_object_or_404(Soal, pk=soal_id, ujian__guru=request.user)  # Hanya guru yang membuat ujian bisa mengedit soal
    if request.method == 'POST':
        form = SoalForm(request.POST, instance=soal)
        if form.is_valid():
            form.save()
            return redirect('soal_list', ujian_id=soal.ujian.id)
    else:
        form = SoalForm(instance=soal)
    return render(request, 'exams/soal_form.html', {'form': form, 'ujian': soal.ujian})

# Delete Soal
@login_required
def soal_delete(request, soal_id):
    soal = get_object_or_404(Soal, pk=soal_id, ujian__guru=request.user)  # Hanya guru yang membuat ujian bisa menghapus soal
    if request.method == 'POST':
        ujian_id = soal.ujian.id
        soal.delete()
        return redirect('soal_list', ujian_id=ujian_id)
    return render(request, 'exams/soal_confirm_delete.html', {'soal': soal})

@login_required
def akses_ujian(request):
    if request.method == 'POST':
        code = request.POST.get('code')
        try:
            ujian = Ujian.objects.get(code=code)
            # Render halaman konfirmasi
            return render(request, 'exams/confirm_ujian.html', {'ujian': ujian})
        except Ujian.DoesNotExist:
            error = "Code ujian tidak valid."
            return render(request, 'exams/akses_ujian.html', {'error': error})
    return render(request, 'exams/akses_ujian.html')


@login_required
def kerjakan_ujian(request, ujian_id):
    ujian = get_object_or_404(Ujian, pk=ujian_id)
    soal_list = Soal.objects.filter(ujian=ujian)
    now = timezone.now()  # Waktu server dengan timezone
    
    # Debug: Cek waktu sekarang dan waktu ujian
    print("Waktu Sekarang:", now)
    print("Waktu Mulai Ujian:", ujian.waktu_mulai)
    print("Waktu Selesai Ujian:", ujian.waktu_selesai)
    
    # Cek apakah sudah mengerjakan
    if HasilUjian.objects.filter(siswa=request.user, ujian=ujian).exists():
        return redirect('nilai_detail', ujian_id=ujian.id)
    
    # Cek waktu ujian
    if ujian.waktu_mulai and now < ujian.waktu_mulai:
        return render(request, 'exams/belum_mulai.html', {
            'ujian': ujian,
            'now': now  # Kirim ke template untuk debugging
        })
    if ujian.waktu_selesai and now > ujian.waktu_selesai:
        return render(request, 'exams/sudah_selesai.html', {'ujian': ujian})
    
    # ... kode lainnya ...
    
    if request.method == 'POST':
        # Hitung waktu sisa
        waktu_mulai = request.session.get(f'waktu_mulai_{ujian.id}')
        if waktu_mulai:
            waktu_mulai = datetime.fromisoformat(waktu_mulai)
            waktu_habis = waktu_mulai + timedelta(minutes=ujian.durasi_menit)
            if timezone.now() > waktu_habis:
                return render(request, 'exams/waktu_habis.html')
        
        # Proses jawaban seperti sebelumnya
        jawaban_siswa = {}
        benar = 0
        for soal in soal_list:
            jawaban = request.POST.get(f'soal_{soal.id}')
            if jawaban == soal.jawaban_benar:
                benar += 1
        
        nilai = (benar / soal_list.count()) * 100 if soal_list.count() > 0 else 0
        
        HasilUjian.objects.create(
            siswa=request.user,
            ujian=ujian,
            nilai=nilai
        )
        
        # Hapus session waktu
        if f'waktu_mulai_{ujian.id}' in request.session:
            del request.session[f'waktu_mulai_{ujian.id}']
        
        return redirect('nilai_detail', ujian_id=ujian.id)
    
    # Set waktu mulai di session
    request.session[f'waktu_mulai_{ujian.id}'] = timezone.now().isoformat()
    waktu_habis = timezone.now() + timedelta(minutes=ujian.durasi_menit)
    
    return render(request, 'exams/kerjakan_ujian.html', {
        'ujian': ujian,
        'soal_list': soal_list,
        'waktu_habis': waktu_habis.isoformat(),
        'durasi_detik': ujian.durasi_detik
    })

# Untuk siswa melihat nilai mereka
@login_required
def nilai_siswa(request):
    nilai_list = HasilUjian.objects.filter(siswa=request.user)
    return render(request, 'grades/nilai_siswa.html', {
        'nilai_list': nilai_list
    })

# Untuk guru melihat nilai semua siswa
@login_required
def nilai_guru(request, ujian_id):
    ujian = get_object_or_404(Ujian, pk=ujian_id, guru=request.user)
    nilai_list = HasilUjian.objects.filter(ujian=ujian)
    return render(request, 'grades/nilai_guru.html', {
        'ujian': ujian,
        'nilai_list': nilai_list
    })

# Detail nilai per ujian
@login_required
def nilai_detail(request, ujian_id):
    ujian = get_object_or_404(Ujian, pk=ujian_id)
    hasil = get_object_or_404(HasilUjian, siswa=request.user, ujian=ujian)
    return render(request, 'grades/nilai_detail.html', {
        'ujian': ujian,
        'hasil': hasil
    })