from django.conf import settings
from django.contrib.auth.backends import BaseBackend
from django.contrib.auth import authenticate as default_authenticate
from .models import User, Siswa  # Import model custom
from ultralytics import YOLO
import librosa
import numpy as np
import joblib

class VoiceAuthBackend(BaseBackend):
    def authenticate(self, request, username=None, password=None, audio=None):
        user = default_authenticate(request, username=username, password=password)
        
        if not user or not user.is_siswa:
            return None
        
        try:
            siswa = user.siswa
        except Siswa.DoesNotExist:
            return None
        
        if not siswa.voice_model:
            return user  # Login biasa tanpa verifikasi
            
        # Proses verifikasi suara
        try:
            y, sr = librosa.load(audio, sr=16000)
            y = librosa.util.fix_length(y, size=int(16000*3))  # Pastikan durasi 3 detik
            
            mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13)
            delta = librosa.feature.delta(mfcc)
            delta2 = librosa.feature.delta(mfcc, order=2)
            features = np.vstack([mfcc, delta, delta2]).T
            
            gmm = joblib.load(siswa.voice_model.path)
            score = gmm.score(features) / len(features)
            
            if score > -50.0:  # Sesuaikan dengan threshold training
                return user
        except Exception as e:
            print(f"Voice auth failed: {e}")
        
        return None

    def get_user(self, user_id):
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None

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