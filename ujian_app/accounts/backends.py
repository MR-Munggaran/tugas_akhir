import os
import tempfile
from django.conf import settings
from django.contrib.auth.backends import BaseBackend
from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import authenticate as default_authenticate
from django.core.exceptions import ValidationError
from .models import User, Siswa  # Import model custom
from ultralytics import YOLO
import librosa
import numpy as np
import joblib

class VoiceAuthBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        # Autentikasi dasar
        user = super().authenticate(request, username=username, password=password)
        
        # Jika autentikasi dasar gagal
        if not user:
            return None
            
        # Jika user tidak memiliki profil siswa
        if not hasattr(user, 'siswa'):
            return user
            
        # Jika tidak ada model suara, lanjutkan tanpa verifikasi
        if not user.siswa.voice_model:
            return user
            
        # Validasi format audio
        audio_file = kwargs.get('audio')
        if not audio_file:
            return None  # Jangan raise error, sesuaikan dengan alur Django
            
        if not audio_file.name.lower().endswith('.wav'):
            raise ValidationError("Hanya format WAV yang diterima")
            
        # Lakukan verifikasi suara
        if self.verify_voice(user.siswa, audio_file):
            return user
        return None

    def verify_voice(self, siswa, audio_file):
        try:
            # Pastikan model suara ada
            if not siswa.voice_model:
                return False
                
            # Proses audio dengan temporary file
            with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp_audio:
                for chunk in audio_file.chunks():
                    tmp_audio.write(chunk)
                tmp_audio.flush()
                tmp_audio.close()  # Pastikan file ditutup

                # Load audio dengan backend soundfile
                y, sr = librosa.load(
                    tmp_audio.name,
                    sr=16000,
                    mono=True,
                    backend='soundfile'
                )
                
                # Hapus file sementara
                os.unlink(tmp_audio.name)

            # Validasi durasi minimal 3 detik
            if len(y) < 16000*3:
                return False
                
            # Normalisasi audio
            y = librosa.util.normalize(y)
            y = librosa.util.fix_length(y, size=int(16000*3))
            
            # Ekstraksi fitur MFCC
            mfcc = librosa.feature.mfcc(
                y=y, sr=sr, n_mfcc=13,
                n_fft=512, hop_length=256
            )
            delta = librosa.feature.delta(mfcc)
            delta2 = librosa.feature.delta(mfcc, order=2)
            features = np.vstack([mfcc, delta, delta2]).T
            
            # Load model GMM
            gmm = joblib.load(siswa.voice_model.path)
            
            # Hitung skor
            log_likelihood = gmm.score(features)
            z_score = (log_likelihood - gmm.means_[0][0]) / np.sqrt(gmm.covariances_[0][0])
            
            # Thresholding
            threshold = siswa.voice_threshold if siswa.voice_threshold else -50
            return z_score > threshold

        except Exception as e:
            # Gunakan Django logging
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Verifikasi gagal: {str(e)}", exc_info=True)
            return False

class FaceAuthBackend(BaseBackend):
    # Load model once
    yolo_model = YOLO(settings.YOLO_FACE_MODEL)

    def authenticate(self, request, username=None, image=None):
        try:
            user = User.objects.get(username=username)
            if not hasattr(user, 'siswa'):
                return None
                
            # Verify image
            results = self.yolo_model.predict(
                source=image,
                conf=settings.FACE_THRESHOLD,
                verbose=False
            )
            
            for result in results:
                for box in result.boxes:
                    detected_name = self.yolo_model.names[int(box.cls.item())].lower()
                    if detected_name == user.username.lower():
                        return user
            return None
            
        except Exception as e:
            print(f"Face auth error: {e}")
            return None

    def get_user(self, user_id):
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None