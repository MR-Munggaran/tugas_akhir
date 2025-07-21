import uuid
from django.http import JsonResponse
from django.urls import reverse
from django.utils import timezone
from datetime import datetime, timedelta
from django.contrib.auth import update_session_auth_hash
import face_recognition
from ultralytics import YOLO
from django.conf import settings
from PIL import Image
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test

from .utils import augment_face_images, extract_mfcc, preprocess_face_image
from .forms import FaceTestImageForm, GuruProfileForm, GuruRegistrationForm, SiswaCreationForm, SiswaForm, KelasForm, SiswaProfileForm,UjianForm, SoalForm, UserEditForm, VoiceUploadForm
from .models import FaceTestImage, JawabanSiswa, ProctoringLog, Siswa, Kelas, LogMasukStudent, User, Ujian, Soal, HasilUjian, UserFace, VoiceData, VoiceSample

from pydub import AudioSegment
import os
import librosa
import soundfile as sf
import numpy as np
from sklearn.preprocessing import StandardScaler
from sklearn.mixture import GaussianMixture
import joblib
import io
from django.core.files.base import ContentFile
from django.views.decorators.http import require_http_methods
from django.contrib import messages
from django.shortcuts import get_object_or_404

yolo_model = YOLO(settings.YOLO_FACE_MODEL)
ubm_voice = settings.VOICE_UBM



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
@require_http_methods(["GET", "POST"])
def login_view(request):
    """
    Login view: siswa akan diarahkan ke face verification,
    guru/admin langsung masuk ke dashboard.
    """
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')

        if not username or not password:
            messages.error(request, 'Username dan password wajib diisi.')
            return render(request, 'accounts/login.html')

        user = authenticate(request, username=username, password=password)
        if user is None:
            messages.error(request, 'Autentikasi gagal. Periksa kembali credentials.')
            return render(request, 'accounts/login.html')

        if not user.is_active:
            messages.error(request, 'Akun Anda belum aktif. Hubungi administrator.')
            return render(request, 'accounts/login.html')

        # Bersihkan sisa‐sisa session verifikasi sebelumnya
        for key in ['pre_verified_user', 'face_attempts', 'face_verified_user', 'voice_attempts']:
            request.session.pop(key, None)

        # Branching: siswa vs guru/admin
        if getattr(user, 'is_siswa', False):
            request.session['pre_verified_user'] = user.id
            # return redirect('face_verification')
            return redirect('voice_verification')
        else:
            login(request, user)
            return redirect('dashboard')

    # GET
    return render(request, 'accounts/login.html')
    
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


# def extract_mfcc(file_path, n_mfcc=13):
#     try:
#         temp_wav = file_path + ".wav_conv"
#         AudioSegment.from_file(file_path).export(temp_wav, format="wav")
#         audio, sr = sf.read(temp_wav, dtype='float32')
#         if audio.ndim > 1:
#             audio = np.mean(audio, axis=1)
#         mfcc = librosa.feature.mfcc(y=audio, sr=sr, n_mfcc=n_mfcc)
#         os.remove(temp_wav)
#         return mfcc.T  # transpose supaya frame x fitur
#     except Exception as e:
#         print(f"[ERROR] extract_mfcc failed: {e}")
#         if os.path.exists(temp_wav):
#             os.remove(temp_wav)
#         return None

@login_required
@user_passes_test(is_guru_or_admin)
def voice_upload(request, student_id):
    student = get_object_or_404(Siswa, pk=student_id)
    user = student.user
    form = VoiceUploadForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        files = request.FILES.getlist('audio')
        if not files:
            form.add_error('audio', 'Upload minimal satu file audio')
        else:
            # Load UBM global scaler dan model
            ubm_data = joblib.load(ubm_voice)
            ubm_scaler = ubm_data['scaler']
            ubm_gmm = ubm_data['ubm']

            all_mfcc = []
            user_train_dir = os.path.join(settings.MEDIA_ROOT, 'voice_train', str(user.id))
            os.makedirs(user_train_dir, exist_ok=True)

            for f in files:
                filename = f"{uuid.uuid4()}_{f.name}"
                save_path = os.path.join(user_train_dir, filename)
                with open(save_path, 'wb') as fh:
                    for chunk in f.chunks():
                        fh.write(chunk)

                VoiceSample.objects.create(user=user, audio_file=os.path.join('voice_train', str(user.id), filename))

                feats = extract_mfcc(save_path)
                if feats is not None:
                    all_mfcc.append(feats)

            if not all_mfcc:
                form.add_error('audio', 'Ekstraksi fitur gagal untuk semua file')
            else:
                data = np.vstack(all_mfcc)
                # Gunakan scaler UBM untuk standarisasi fitur
                scaled = ubm_scaler.transform(data)

                # Latih GMM model user
                gmm_user = GaussianMixture(n_components=8, covariance_type='diag', n_init=3, random_state=42)
                gmm_user.fit(scaled)

                # Hitung log-likelihood ratio user dan UBM pada data pelatihan
                ll_user = gmm_user.score(scaled)
                ll_ubm = ubm_gmm.score(scaled)
                llr = ll_user - ll_ubm

                mean_llr = np.mean(llr)
                std_llr = np.std(llr)
                threshold = float(mean_llr - 0.5 * std_llr)

                vd, _ = VoiceData.objects.get_or_create(user=user)
                buf_s, buf_g = io.BytesIO(), io.BytesIO()
                joblib.dump(ubm_scaler, buf_s)    # Simpan scaler UBM ke user model (bisa dipakai saat verifikasi)
                joblib.dump(gmm_user, buf_g)      # Simpan model user
                vd.scaler_model = buf_s.getvalue()
                vd.gmm_model = buf_g.getvalue()
                vd.threshold = threshold
                vd.is_trained = True
                vd.save()

                # Simpan juga model dan scaler ke file agar bisa diakses untuk evaluasi / backup
                user_model_dir = os.path.join(settings.MEDIA_ROOT, 'voice_models', str(user.id))
                os.makedirs(user_model_dir, exist_ok=True)

                scaler_file_path = os.path.join(user_model_dir, 'scaler.joblib')
                gmm_file_path = os.path.join(user_model_dir, 'gmm.joblib')

                with open(scaler_file_path, 'wb') as f_s:
                    f_s.write(buf_s.getvalue())

                with open(gmm_file_path, 'wb') as f_g:
                    f_g.write(buf_g.getvalue())

                print(f"[DEBUG] mean_llr={mean_llr}, std_llr={std_llr}, threshold={threshold}")
                print(f"[DEBUG] Model dan scaler juga disimpan di: {user_model_dir}")

                return redirect('student_list')

    return render(request, 'students/upload_voice.html', {'form': form, 'student': student})

def verify_voice(user, audio_file):
    vd = VoiceData.objects.get(user=user)
    # Load scaler dan model user
    scaler = joblib.load(io.BytesIO(vd.scaler_model))
    gmm_user = joblib.load(io.BytesIO(vd.gmm_model))

    # Load UBM global (scaler dan model)
    ubm_data = joblib.load(ubm_voice)
    ubm_scaler = ubm_data['scaler']
    ubm_gmm = ubm_data['ubm']

    margin = vd.margin

    temp = f"verify_{user.id}.tmp"
    with open(temp, 'wb') as f:
        for chunk in audio_file.chunks():
            f.write(chunk)
    try:
        mfcc = extract_mfcc(temp)
        if mfcc is None:
            return False

        # Standarisasi pakai scaler UBM
        scaled = ubm_scaler.transform(mfcc)

        # Hitung log-likelihood user dan UBM
        ll_user = gmm_user.score(scaled)
        ll_ubm = ubm_gmm.score(scaled)

        llr = ll_user - ll_ubm

        adjusted_threshold = vd.threshold - margin

        print(f"[DEBUG] User: {user.username}, llr={llr:.2f}, threshold={vd.threshold:.2f}, margin={margin:.2f}, adj_thresh={adjusted_threshold:.2f}")

        return llr > adjusted_threshold
    finally:
        os.remove(temp)
        
@login_required
@user_passes_test(is_guru_or_admin)
def delete_voice_samples(request, student_id):
    if request.method == 'POST':
        student = get_object_or_404(Siswa, pk=student_id)
        user = student.user
        samples = VoiceSample.objects.filter(user=user)

        # Hapus file dan record voice samples
        for sample in samples:
            sample.audio_file.delete(save=False)  # hapus file fisik
        samples.delete()  # hapus record di DB

        messages.success(request, f"Semua sample suara untuk {student.nama_lengkap} telah dihapus.")
        return redirect('student_list')
    else:
        messages.error(request, "Metode request tidak diizinkan.")
        return redirect('student_list')

def voice_verification(request):
    user_id = request.session.get('pre_verified_user')
    if not user_id:
        return redirect('login')
    
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return redirect('login')
    
    if request.method == 'POST':
        audio = request.FILES.get('audio')
        if not audio:
            return JsonResponse({'error': 'Rekam suara terlebih dahulu'})
        if verify_voice(user, audio):
            request.session['voice_verified_user'] = user.id
            request.session.pop('voice_attempts', None)
            return JsonResponse({'redirect': reverse('face_verification')})  # arahkan ke face
        attempts = request.session.get('voice_attempts', 0) + 1
        request.session['voice_attempts'] = attempts
        if attempts >= 3:
            request.session.flush()
            return redirect('login')
        return JsonResponse({'error': f'Gagal verifikasi ({attempts}/3)'})
    return render(request, 'accounts/voice_verification.html', {'remaining': 3 - request.session.get('voice_attempts', 0)})

@login_required
def enroll_face(request, pk):
    siswa = get_object_or_404(Siswa, pk=pk)
    user = siswa.user

    if request.method == 'POST':
        image = request.FILES.get('image')
        if not image:
            return render(request, 'students/face_enroll.html', {
                'error': 'Gambar tidak ditemukan', 'student': siswa
            })

        try:
            # 1. Preprocessing: deteksi + crop wajah
            face_img: Image.Image = preprocess_face_image(image)

            # 2. Ekstrak encoding wajah dari hasil crop (original)
            face_array = np.array(face_img)
            face_location = [(0, face_array.shape[1], face_array.shape[0], 0)]
            encodings = face_recognition.face_encodings(face_array, face_location)
            if not encodings:
                return render(request, 'students/face_enroll.html', {
                    'error': 'Face recognition gagal ekstrak fitur wajah.', 'student': siswa
                })
            encoding = encodings[0]

            # 3. Augmentasi: hasilkan beberapa versi gambar
            augmented_faces = augment_face_images(face_img)  # List[PIL.Image]

            # 4. Simpan setiap augmented image ke MEDIA_ROOT/<username>_faces/…
            saved_files = []  # untuk melacak nama‐nama file yang berhasil disimpan

            # Pastikan direktori : MEDIA_ROOT/faces/<username>/
            user_folder = os.path.join(settings.MEDIA_ROOT, 'faces', user.username)
            os.makedirs(user_folder, exist_ok=True)

            for idx, aug_img in enumerate(augmented_faces):
                # Buat nama file unik, misalnya: face_<uuid4>_<idx>.jpg
                filename = f"face_{uuid.uuid4().hex[:8]}_{idx}.jpg"
                filepath = os.path.join(user_folder, filename)

                # Simpan ke filesystem
                aug_img_rgb = aug_img.convert('RGB')  # pastikan RGB
                aug_img_rgb.save(filepath, format='JPEG')

                saved_files.append(os.path.join('faces', user.username, filename))

            # 5. (Opsional) Simpan salah satu foto (default: original crop) ke model UserFace
            #    atau Anda bisa menyimpan semua path hasil augmentasi ke model lain jika diinginkan.

            # Contoh: update_only satu foto & encoding di UserFace (seperti semula)
            #    photo: kami gunakan file original crop (idx==0)
            buffer = io.BytesIO()
            augmented_faces[0].save(buffer, format='JPEG')
            image_file = ContentFile(buffer.getvalue(), f'{user.username}_face.jpg')

            UserFace.objects.update_or_create(
                user=user,
                defaults={
                    'encoding': encoding.tobytes(),
                    'photo': image_file
                }
            )

            return render(request, 'students/face_enroll.html', {
                'success': 'Wajah berhasil disimpan dan di‐augmentasi!', 
                'student': siswa,
                'saved_images': saved_files  # Anda bisa tampilkan daftar path jika mau
            })

        except ValueError as ve:
            # Misalnya kalau tidak ada wajah terdeteksi
            return render(request, 'students/face_enroll.html', {
                'error': str(ve), 'student': siswa
            })

        except Exception as e:
            print(f"[ERROR] Gagal menyimpan wajah: {str(e)}")
            return render(request, 'students/face_enroll.html', {
                'error': 'Terjadi kesalahan saat memproses gambar.', 'student': siswa
            })

    return render(request, 'students/face_enroll.html', {'student': siswa})

@login_required
def delete_face(request, pk):
    siswa = get_object_or_404(Siswa, pk=pk)
    user = siswa.user

    try:
        user_face = UserFace.objects.get(user=user)
        user_face.delete()
        messages.success(request, 'Data wajah berhasil dihapus.')
    except UserFace.DoesNotExist:
        messages.error(request, 'Data wajah tidak ditemukan.')

    return redirect('students/face_enroll.html', {'student': siswa})

def verify_face(user, image_file):
    """
    - Deteksi wajah dengan YOLO.
    - Jika TIDAK ada wajah terdeteksi: langsung return False (tidak menyimpan file apa pun).
    - Jika wajah terdeteksi:
        • Crop wajah (bounding box pertama).
        • Simpan crop‐an di MEDIA_ROOT/detected_faces/ dengan nama unik.
        • Lakukan face encoding & matching, lalu kembalikan True/False.
    """
    try:
        # 1. Buka file gambar, cek integritas, lalu convert ke RGB
        img = Image.open(image_file)
        img.verify()
        image_file.seek(0)
        img = Image.open(image_file).convert("RGB")
        img_array = np.array(img)

        # 2. Deteksi wajah dengan YOLO (asumsikan yolo_model sudah didefinisikan)
        results = yolo_model(img_array)[0]
        boxes = results.boxes.xyxy.cpu().numpy()  # format: [[x1, y1, x2, y2], ...]

        # 3. Jika tidak ada wajah, langsung return False (tidak menyimpan apa‐apa)
        if len(boxes) == 0:
            print("[INFO] Tidak ada wajah terdeteksi oleh YOLO. Tidak menyimpan file.")
            return False

        # 4. Ambil bounding box wajah pertama (x1, y1, x2, y2)
        x1, y1, x2, y2 = boxes[0][:4].astype(int)
        top    = max(0, y1)
        left   = max(0, x1)
        bottom = min(img_array.shape[0], y2)
        right  = min(img_array.shape[1], x2)

        # 5. Crop wajah
        face_img = img.crop((left, top, right, bottom))

        # 6. Buat folder 'detected_faces' di MEDIA_ROOT jika belum ada
        folder_faces = os.path.join(settings.MEDIA_ROOT, "detected_faces")
        os.makedirs(folder_faces, exist_ok=True)

        # 7. Simpan crop wajah ke disk
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_id = str(uuid.uuid4())[:8]
        filename = f"{user.username}_{timestamp}_{unique_id}.jpg"
        save_path = os.path.join(folder_faces, filename)
        face_img.save(save_path, format="JPEG")
        print(f"[INFO] Wajah terdeteksi, crop disimpan di: {save_path}")

        # 8. Lanjutkan face encoding untuk matching
        #    Kita bisa pakai img_array & wajah yang terdeteksi (face_location)
        face_location = [(top, right, bottom, left)]
        uploaded_encodings = face_recognition.face_encodings(img_array, face_location)
        if not uploaded_encodings:
            print("[INFO] Gagal ekstrak encoding wajah meski kotak terdeteksi.")
            return False

        uploaded_encoding = uploaded_encodings[0]

        # 9. Ambil encoding yang sudah tersimpan untuk user
        try:
            user_face = UserFace.objects.get(user=user)
            known_encoding = np.frombuffer(user_face.encoding)
        except UserFace.DoesNotExist:
            print("[ERROR] User belum punya data wajah.")
            return False

        # 10. Hitung jarak dan tentukan match atau tidak
        distance  = face_recognition.face_distance([known_encoding], uploaded_encoding)[0]
        threshold = getattr(settings, "FACE_THRESHOLD", 0.45)
        is_match  = distance <= threshold

        if is_match:
            print(f"[INFO] Wajah cocok (distance={distance:.4f} ≤ {threshold}).")
        else:
            print(f"[INFO] Wajah tidak cocok (distance={distance:.4f} > {threshold}).")

        return is_match

    except Exception as e:
        print(f"[ERROR] Gagal verifikasi wajah: {str(e)}")
        return False

def face_verification(request):
    user_id = request.session.get('voice_verified_user')
    if not user_id:
        return redirect('login')
    
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return redirect('login')
    
    if request.method == 'POST':
        image = request.FILES.get('image')
        if not image:
            return render(request, 'accounts/face_verification.html', {'error': 'Gambar tidak ditemukan'})
        
        verified = verify_face(user, image)
        attempts = request.session.get('face_attempts', 0)
        
        if verified:
            for key in ['voice_verified_user', 'face_attempts']:
                request.session.pop(key, None)
            user.backend = 'django.contrib.auth.backends.ModelBackend'
            login(request, user)
            return redirect('dashboard')
        
        attempts += 1
        request.session['face_attempts'] = attempts
        
        if attempts >= 3:
            request.session.flush()
            return redirect('login')
            
        return render(request, 'accounts/face_verification.html', {
            'error': f'Verifikasi gagal ({attempts}/3)',
            'remaining': 3 - attempts
        })
    
    return render(request, 'accounts/face_verification.html', {
        'remaining': 3 - request.session.get('face_attempts', 0)
    })

def preprocess_face_image(uploaded_image_file):
    img = Image.open(uploaded_image_file)
    img.verify()
    uploaded_image_file.seek(0)
    img = Image.open(uploaded_image_file).convert('RGB')
    img_array = np.array(img)

    results = yolo_model(img_array)[0]
    boxes = results.boxes.xyxy.cpu().numpy()
    if len(boxes) == 0:
        raise ValueError("Wajah tidak terdeteksi oleh YOLO.")

    x1, y1, x2, y2 = boxes[0][:4].astype(int)
    top = max(0, y1)
    right = min(img_array.shape[1], x2)
    bottom = min(img_array.shape[0], y2)
    left = max(0, x1)
    face_crop = img.crop((left, top, right, bottom))
    return face_crop

def test_face(request, pk):
    siswa = get_object_or_404(Siswa, pk=pk)
    user = siswa.user

    saved_image_url = None
    error = None

    if request.method == 'POST':
        form = FaceTestImageForm(request.POST, request.FILES)
        if form.is_valid():
            image_file = form.cleaned_data['image']
            try:
                # Preprocessing wajah pakai YOLO
                face_img = preprocess_face_image(image_file)

                # Ekstrak encoding wajah dari crop hasil YOLO
                face_array = np.array(face_img)
                face_location = [(0, face_array.shape[1], face_array.shape[0], 0)]
                encodings = face_recognition.face_encodings(face_array, face_location)
                if not encodings:
                    raise ValueError("Gagal ekstrak fitur wajah.")
                encoding = encodings[0]

                # Simpan file hasil crop ke MEDIA_ROOT/face_tests/<username>/
                user_folder = os.path.join(settings.MEDIA_ROOT, 'face_tests', user.username)
                os.makedirs(user_folder, exist_ok=True)

                filename = f"test_{uuid.uuid4().hex[:8]}.jpg"
                filepath = os.path.join(user_folder, filename)
                face_img_rgb = face_img.convert('RGB')
                face_img_rgb.save(filepath, format='JPEG')

                # Simpan record ke DB
                face_test = FaceTestImage.objects.create(
                    user=user,
                    image=os.path.join('face_tests', user.username, filename),
                    encoding=encoding.tobytes()
                )

                saved_image_url = face_test.image.url

            except ValueError as ve:
                error = str(ve)
            except Exception as e:
                error = "Terjadi kesalahan saat memproses gambar."
                print(f"[ERROR] {e}")

    else:
        form = FaceTestImageForm()

    return render(request, 'students/face_test.html', {
        'student': siswa,
        'form': form,
        'saved_image_url': saved_image_url,
        'error': error,
    })

import base64
import matplotlib.pyplot as plt
from django.shortcuts import render
from sklearn.metrics import confusion_matrix, classification_report

def bytes_to_encoding(enc_bytes):
    return np.frombuffer(enc_bytes, dtype=np.float64)

def calculate_distance(enc1, enc2):
    return np.linalg.norm(enc1 - enc2)

def evaluate_face_recognition_with_names():
    user_faces = UserFace.objects.all()
    test_faces = FaceTestImage.objects.all()

    user_ids = sorted(set([uf.user_id for uf in user_faces] + [tf.user_id for tf in test_faces]))

    # Mapping user_id ke nama kelas string
    id_to_name = {uid: f"User {uid}" for uid in user_ids}
    id_to_name[-1] = "No Match"  # label khusus untuk prediksi gagal match

    y_true = []
    y_pred = []

    threshold = 0.6
    user_encodings = {uf.user_id: bytes_to_encoding(uf.encoding) for uf in user_faces}

    for test in test_faces:
        true_user_id = test.user_id
        test_encoding = bytes_to_encoding(test.encoding)

        distances = []
        user_ids_enc = []

        for user_id, enroll_encoding in user_encodings.items():
            dist = calculate_distance(test_encoding, enroll_encoding)
            distances.append(dist)
            user_ids_enc.append(user_id)

        if distances:
            min_dist_idx = np.argmin(distances)
            predicted_user_id = user_ids_enc[min_dist_idx] if distances[min_dist_idx] <= threshold else -1
        else:
            predicted_user_id = -1

        # Simpan nama kelas sesuai mapping
        y_true.append(id_to_name[true_user_id])
        y_pred.append(id_to_name[predicted_user_id])

    class_names = list(id_to_name.values())

    cm = confusion_matrix(y_true, y_pred, labels=class_names)
    report = classification_report(y_true, y_pred, labels=class_names, output_dict=True)

    return cm, class_names, report

def plot_confusion_matrix(cm, classes):
    plt.figure(figsize=(8, 6))
    plt.imshow(cm, interpolation='nearest', cmap=plt.cm.Blues)
    plt.title('Confusion Matrix')
    plt.colorbar()

    tick_marks = range(len(classes))
    plt.xticks(tick_marks, classes, rotation=45, ha='right')
    plt.yticks(tick_marks, classes)

    thresh = cm.max() / 2
    for i, j in np.ndindex(cm.shape):
        plt.text(j, i, format(cm[i, j], 'd'),
                 horizontalalignment="center",
                 color="white" if cm[i, j] > thresh else "black")

    plt.ylabel('True label')
    plt.xlabel('Predicted label')
    plt.tight_layout()

    buf = io.BytesIO()
    plt.savefig(buf, format='png')
    plt.close()
    buf.seek(0)

    img_base64 = base64.b64encode(buf.getvalue()).decode('utf-8')
    return img_base64

def face_evaluation_view(request):
    cm, class_names, report = evaluate_face_recognition_with_names()

    # Ubah key 'f1-score' ke 'f1_score' supaya mudah diakses di template
    for label, metrics in report.items():
        if isinstance(metrics, dict) and 'f1-score' in metrics:
            metrics['f1_score'] = metrics.pop('f1-score')

    cm_image = plot_confusion_matrix(cm, class_names)

    context = {
        'confusion_matrix': cm.tolist(),
        'classification_report': report,
        'cm_image': cm_image,
        'class_names': class_names,
    }
    return render(request, 'students/face_evaluation.html', context)

def verify_voice_test(user, file_path):
    vd = VoiceData.objects.get(user=user)
    scaler = joblib.load(io.BytesIO(vd.scaler_model))
    gmm_user = joblib.load(io.BytesIO(vd.gmm_model))

    ubm_data = joblib.load(ubm_voice)
    ubm_scaler = ubm_data['scaler']
    ubm_gmm = ubm_data['ubm']

    margin = vd.margin

    # langsung proses file dari path
    mfcc = extract_mfcc(file_path)
    if mfcc is None:
        return False

    scaled = ubm_scaler.transform(mfcc)
    ll_user = gmm_user.score(scaled)
    ll_ubm = ubm_gmm.score(scaled)
    llr = ll_user - ll_ubm

    adjusted_threshold = vd.threshold - margin

    print(f"[DEBUG] User: {user.username}, llr={llr:.2f}, threshold={vd.threshold:.2f}, margin={margin:.2f}, adj_thresh={adjusted_threshold:.2f}")

    return llr > adjusted_threshold

def evaluate_voice_recognition():
    test_samples = VoiceSample.objects.all()
    voice_models = {vd.user_id: vd for vd in VoiceData.objects.filter(is_trained=True)}

    y_true = []
    y_pred = []

    user_ids = sorted(set(sample.user_id for sample in test_samples))
    id_to_name = {uid: f"User {uid}" for uid in user_ids}
    id_to_name[-1] = "No Match"

    for sample in test_samples:
        true_user = sample.user

        # Skip jika model tidak tersedia
        if true_user.id not in voice_models:
            continue

        vd = voice_models[true_user.id]
        audio_path = sample.audio_file.path

        with open(audio_path, 'rb') as audio_file:
            is_match = verify_voice_test(true_user, audio_path)

        y_true.append(id_to_name[true_user.id])
        if is_match:
            y_pred.append(id_to_name[true_user.id])
        else:
            y_pred.append(id_to_name[-1])

    class_names = list(id_to_name.values())
    labels = class_names

    cm = confusion_matrix(y_true, y_pred, labels=labels)
    report = classification_report(y_true, y_pred, labels=labels, output_dict=True)

    return cm, class_names, report

def plot_confusion_matrix(cm, classes):
    plt.figure(figsize=(8,6))
    plt.imshow(cm, interpolation='nearest', cmap=plt.cm.Blues)
    plt.title('Confusion Matrix')
    plt.colorbar()
    tick_marks = range(len(classes))
    plt.xticks(tick_marks, classes, rotation=45, ha='right')
    plt.yticks(tick_marks, classes)
    thresh = cm.max() / 2

    for i, j in np.ndindex(cm.shape):
        plt.text(j, i, format(cm[i,j], 'd'), ha='center', va='center',
                 color='white' if cm[i,j] > thresh else 'black')

    plt.xlabel('Predicted label')
    plt.ylabel('True label')
    plt.tight_layout()

    buf = io.BytesIO()
    plt.savefig(buf, format='png')
    plt.close()
    buf.seek(0)
    return base64.b64encode(buf.getvalue()).decode('utf-8')

@login_required
@user_passes_test(is_guru_or_admin)
def voice_evaluation_view(request):
    cm, class_names, report = evaluate_voice_recognition()

    # Rename key f1-score ke f1_score supaya template mudah akses
    for label, metrics in report.items():
        if isinstance(metrics, dict) and 'f1-score' in metrics:
            metrics['f1_score'] = metrics.pop('f1-score')

    cm_image = plot_confusion_matrix(cm, class_names)

    # Buat list pasangan (row_confusion_matrix, class_name)
    confusion_data = list(zip(cm.tolist(), class_names))

    context = {
        'confusion_data': confusion_data,
        'classification_report': report,
        'cm_image': cm_image,
        'class_names': class_names,
    }
    return render(request, 'students/voice_evaluation.html', context)
