from django.conf import settings
from django.contrib.auth.backends import BaseBackend
from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import authenticate as default_authenticate
from django.core.exceptions import ValidationError
from .models import User, Siswa  # Import model custom
from ultralytics import YOLO

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