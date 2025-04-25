import os
import tempfile
import traceback
from django.http import HttpResponseForbidden, JsonResponse
from django.utils import timezone
from datetime import datetime, timedelta
from django.contrib.auth import update_session_auth_hash
from django.core.exceptions import ObjectDoesNotExist
import joblib
import librosa
from scipy import stats
import numpy as np
from ultralytics import YOLO
from django.conf import settings
from PIL import Image
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from .forms import GuruProfileForm, GuruRegistrationForm, SiswaCreationForm, SiswaForm, KelasForm, SiswaProfileForm, UjianForm, SoalForm, UserEditForm, VoiceModelForm
from .models import JawabanSiswa, ProctoringLog, Siswa, Kelas, LogMasukStudent, User, Ujian, Soal, HasilUjian


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
            # Jika user adalah siswa DAN memiliki model suara
            if user.is_siswa and hasattr(user, 'siswa') and user.siswa.voice_model:
                request.session['pre_verified_user'] = user.id
                request.session['voice_attempts'] = 0
                return redirect('voice_verification')
            else:
                # Login langsung untuk guru/admin atau siswa tanpa model suara
                login(request, user)
                return redirect('dashboard')
        else:
            return render(request, 'accounts/login.html', {'error': 'Autentikasi gagal'})
    return render(request, 'accounts/login.html')

def voice_verification(request):
    try:
        user_id = request.session.get('pre_verified_user')
        if not user_id:
            return redirect('login')
        
        user = User.objects.select_related('siswa').get(id=user_id)
        siswa = user.siswa
        
        if not hasattr(siswa, 'voice_model') or not siswa.voice_model:
            login(request, user)
            return redirect('dashboard')
            
    except ObjectDoesNotExist:
        return redirect('login')

    if request.method == 'POST':
        audio = request.FILES.get('audio')
        if not audio:
            return render(request, 'accounts/voice_verification.html', {
                'error': 'Harap unggah file audio'
            })

        # Validasi format file
        if not audio.name.lower().endswith('.wav'):
            return render(request, 'accounts/voice_verification.html', {
                'error': 'Hanya format WAV yang didukung'
            })

        if audio.size > 5*1024*1024:
            return render(request, 'accounts/voice_verification.html', {
                'error': 'Ukuran file terlalu besar (maks 5MB)'
            })

        try:
            verified, confidence = verify_voice(siswa, audio)
            if verified:
                request.session['voice_verified'] = True
                request.session.pop('voice_attempts', None)
                login(request, user)
                return redirect('dashboard')
                
        except Exception as e:
            error_traceback = traceback.format_exc()
            with open("voice_verification_errors.log", "a") as log_file:
                log_file.write(f"Error: {str(e)}\nTraceback:\n{error_traceback}\n")
            error_msg = str(e) if str(e) else 'Kesalahan verifikasi suara'
            return render(request, 'accounts/voice_verification.html', {
                'error': error_msg
            })

        attempts = request.session.get('voice_attempts', 0) + 1
        request.session['voice_attempts'] = attempts
        
        if attempts >= 3:
            request.session.flush()
            return redirect('login')
            
        return render(request, 'accounts/voice_verification.html', {
            'error': f'Verifikasi gagal ({attempts}/3)',
            'remaining': 3 - attempts
        })
    
    return render(request, 'accounts/voice_verification.html')
    
def verify_voice(siswa, audio_file):
    try:
        # Load model
        if not os.path.exists('voice_models/ubm.joblib'):
            raise FileNotFoundError("Model UBM tidak ditemukan")
        if not siswa.voice_model:
            raise ValueError("Model suara pengguna tidak tersedia")
            
        ubm = joblib.load('voice_models/ubm.joblib')
        speaker_gmm = joblib.load(siswa.voice_model.path)
        
        # Proses audio
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
            for chunk in audio_file.chunks():
                tmp.write(chunk)
            tmp.flush()
            tmp.close()

            # Validasi audio
            try:
                y, sr = librosa.load(tmp.name, sr=16000, mono=True)
            except Exception as e:
                raise ValueError(f"File audio rusak/tidak valid: {str(e)}")

            os.unlink(tmp.name)
            
        # Validasi durasi
        if len(y) < 16000*3:
            raise ValueError("Durasi rekaman kurang dari 3 detik")
            
        # Ekstraksi fitur
        mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13, n_fft=512, hop_length=256)
        if mfcc.shape[1] < 10:  # Minimal 10 frame
            raise ValueError("Fitur audio tidak mencukupi")
                # Ekstraksi fitur MFCC (pastikan parameter sama dengan training)
        delta = librosa.feature.delta(mfcc)
        delta2 = librosa.feature.delta(mfcc, order=2)
        features = np.vstack([mfcc, delta, delta2]).T
            
        # Verifikasi
        speaker_score = speaker_gmm.score(features)
        ubm_score = ubm.score(features)
        llr = speaker_score - ubm_score
        
        # Normalisasi
        z_score = stats.zscore([llr])[0]
        normalized_score = 1 / (1 + np.exp(-z_score))
        
        threshold = siswa.voice_threshold if siswa.voice_threshold else -50
        if normalized_score <= threshold:
            raise ValueError(f"Skor terlalu rendah ({normalized_score:.2f} <= {threshold})")
            
        return True, normalized_score

    except Exception as e:
        error_msg = f"Verification failed: {str(e)}"
        print(error_msg)
        with open("voice_verification_errors.log", "a") as log_file:
            log_file.write(f"{error_msg}\n")
        return False, 0.0
    
# Load model once at startup
yolo_model = YOLO(settings.YOLO_FACE_MODEL)

def verify_face(user, image_file):
    try:
        # Validasi gambar
        img = Image.open(image_file)
        img.verify()
        image_file.seek(0)  # Reset pointer
        
        # Konversi ke RGB dan kembalikan sebagai PIL Image
        img = Image.open(image_file).convert('RGB')
        
        # Prediksi menggunakan YOLOv8 dengan PIL Image
        results = yolo_model.predict(source=img)  # Langsung kirim PIL Image
        
        # Proses hasil prediksi
        for result in results:
            boxes = result.boxes
            for box in boxes:
                class_idx = int(box.cls.item())
                detected_name = yolo_model.names[class_idx].lower()
                confidence = box.conf.item()
                
                if (detected_name == user.username.lower() and 
                    confidence > getattr(settings, 'FACE_THRESHOLD', 0.7)):
                    return True
        return False

    except Exception as e:
        print(f"[ERROR] Face verification failed: {str(e)}")
        return False

def face_verification(request):
    user_id = request.session.get('pre_verified_user')
    voice_verified = request.session.get('voice_verified', False)
    
    if not user_id or not voice_verified:
        return redirect('login')

    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return redirect('login')

    if request.method == 'POST':
        image = request.FILES.get('image')
        attempts = request.session.get('face_attempts', 0)
        
        # Verifikasi menggunakan user langsung
        verified = verify_face(user, image)

        if verified:
            # Login user
            user.backend = 'accounts.backends.FaceAuthBackend'
            login(request, user)
            
            # Bersihkan session
            for key in ['pre_verified_user', 'voice_verified', 
                       'voice_attempts', 'face_attempts']:
                if key in request.session:
                    del request.session[key]
            
            return redirect('dashboard')
        else:
            attempts += 1
            request.session['face_attempts'] = attempts
            
            if attempts >= 3:
                # Bersihkan semua session
                for key in ['pre_verified_user', 'voice_verified', 
                           'voice_attempts', 'face_attempts']:
                    if key in request.session:
                        del request.session[key]
                return redirect('login')
            
            return render(request, 'accounts/face_verification.html', {
                'error': f'Verifikasi gagal ({attempts}/3)',
                'remaining': 3 - attempts
            })
    
    return render(request, 'accounts/face_verification.html', {
        'remaining': 3 - request.session.get('face_attempts', 0)
    })

# Logout
@login_required
def logout_view(request):
    logout(request)
    return redirect('login')

# Dashboard
@login_required
def dashboard(request):
    context = {}
    
    if request.user.is_guru:
        context['jumlah_siswa'] = Siswa.objects.count()
        context['jumlah_ujian'] = Ujian.objects.filter(guru=request.user).count()
        context['nama_guru'] = request.user.guru.nama_lengkap
    
    elif request.user.is_siswa:
        try:
            siswa = request.user.siswa
            context['siswa'] = siswa
            hasil_ujian = HasilUjian.objects.filter(siswa=request.user).order_by('-tanggal_selesai')
            
            context['jumlah_ujian_diikuti'] = hasil_ujian.count()
            context['nilai_terakhir'] = hasil_ujian.first() if hasil_ujian.exists() else None
            
        except Siswa.DoesNotExist:
            pass
    
    return render(request, 'accounts/dashboard.html', context)

@login_required
def edit_profile(request):
    user = request.user
    profile_instance = user.guru if user.is_guru else user.siswa if user.is_siswa else None
    
    if request.method == 'POST':
        user_form = UserEditForm(request.POST, instance=user)
        profile_form = (GuruProfileForm(request.POST, instance=profile_instance) if user.is_guru 
                      else SiswaProfileForm(request.POST, instance=profile_instance))
        
        if user_form.is_valid() and profile_form.is_valid():
            # Update password jika diisi
            new_password = user_form.cleaned_data.get('new_password')
            if new_password:
                user.set_password(new_password)
                update_session_auth_hash(request, user)
            
            user_form.save()
            profile_form.save()
            return redirect('dashboard')
    else:
        user_form = UserEditForm(instance=user)
        profile_form = (GuruProfileForm(instance=profile_instance) if user.is_guru 
                      else SiswaProfileForm(instance=profile_instance))

    return render(request, 'accounts/edit_profile.html', {
        'user_form': user_form,
        'profile_form': profile_form
    })

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

def upload_voice_model(request, pk):
    siswa = get_object_or_404(Siswa, pk=pk)
    
    # Hanya guru atau admin yang bisa mengupload
    if not request.user.is_guru and not request.user.is_superuser:
        return HttpResponseForbidden("Anda tidak memiliki akses")
    
    if request.method == 'POST':
        form = VoiceModelForm(request.POST, request.FILES, instance=siswa)
        if form.is_valid():
            form.save()
            return redirect('student_list')
    else:
        form = VoiceModelForm(instance=siswa)
    
    return render(request, 'students/upload_voice.html', {
        'form': form,
        'siswa': siswa
    })

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
            if jawaban:
                # Simpan jawaban ke model JawabanSiswa
                JawabanSiswa.objects.update_or_create(
                    siswa=request.user,
                    soal=soal,
                    defaults={'jawaban': jawaban}
                )
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

def verify_face_proctoring(user, image_file):
    try:
        # Buka gambar dan konversi ke format yang kompatibel
        img = Image.open(image_file).convert("RGB")
        
        # Prediksi dengan model YOLO
        results = yolo_model.predict(source=img)
        
        # Iterasi hasil prediksi
        for result in results:
            boxes = result.boxes
            
            # Skip jika tidak ada deteksi
            if len(boxes) == 0:
                continue  # Tidak ada wajah terdeteksi
            
            # Ambil data deteksi
            class_indices = boxes.cls.cpu().numpy()  # Konversi ke numpy array
            confidences = boxes.conf.cpu().numpy()
            
            # Iterasi setiap deteksi
            for i in range(len(boxes)):
                class_idx = int(class_indices[i])
                confidence = confidences[i]
                detected_name = yolo_model.names[class_idx].lower()
                
                # Kecocokan username dan threshold
                if detected_name == user.username.lower() and confidence > 0.85:
                    return True
                
            # Deteksi multi-wajah
            if len(boxes) > 1:
                print(f"Multiple faces detected for {user.username}")
                return False
        
        return False  # Tidak ada deteksi yang valid

    except Exception as e:
        print(f"[ERROR] Proctoring verification failed: {str(e)}")
        return False
    
@login_required
@csrf_exempt
def proctoring_check(request):
    if request.method == 'POST':
        image = request.FILES.get('image')
        if not image:
            return JsonResponse({'error': 'No image provided'}, status=400)
        
        # Verifikasi wajah
        verified = verify_face_proctoring(request.user, image)
        
        return JsonResponse({'verified': verified})
    
    return JsonResponse({'error': 'Invalid request'}, status=400)

@login_required
def proctoring_logs(request, ujian_id):
    ujian = get_object_or_404(Ujian, pk=ujian_id)
    logs = ProctoringLog.objects.filter(ujian=ujian)
    return render(request, 'exams/proctoring_logs.html', {
        'ujian': ujian,
        'logs': logs
    })

def delete_voice_model(request, pk):
    siswa = get_object_or_404(Siswa, pk=pk)
    
    # Hanya guru atau admin yang bisa menghapus
    if not request.user.is_guru and not request.user.is_superuser:
        return HttpResponseForbidden("Anda tidak memiliki akses")
    
    if request.method == 'POST':
        # Hapus file suara yang terkait
        if siswa.voice_model:  # Ganti dengan field yang sesuai di model Siswa
            siswa.voice_model.delete()
        siswa.save()
        return redirect('student_list')
    
    return render(request, 'students/delete_voice.html', {
        'siswa': siswa
    })