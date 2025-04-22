# accounts/services.py
import cv2
import numpy as np
from ultralytics import YOLO
from django.conf import settings
from sklearn.metrics.pairwise import cosine_similarity
import logging

logger = logging.getLogger(__name__)

class FaceVerifier:
    def __init__(self):
        # Model untuk deteksi wajah
        self.detection_model = YOLO(settings.YOLO_FACE_MODEL)
        # Model untuk ekstraksi embedding
        self.recognition_model = YOLO(settings.YOLO_FACE_RECOGNITION_MODEL)  # Ganti dengan model recognition
        self.similarity_threshold = 0.75
        
    def _process_image(self, image_file):
        img_bytes = image_file.read()
        np_array = np.frombuffer(img_bytes, np.uint8)
        return cv2.imdecode(np_array, cv2.IMREAD_COLOR)
    
    def _get_embedding(self, face_image):
        """Ekstraksi embedding dari wajah yang terdeteksi"""
        # Konversi warna BGR ke RGB
        rgb_image = cv2.cvtColor(face_image, cv2.COLOR_BGR2RGB)
        
        # Ekstraksi embedding menggunakan recognition model
        results = self.recognition_model.predict(
            source=rgb_image,
            imgsz=160,
            verbose=False
        )
        
        if results and hasattr(results[0], 'embeddings'):
            return results[0].embeddings[0].numpy()
        return None
    
    def verify(self, user, image_file):
        try:
            # Validasi dasar gambar
            if image_file.size > 5 * 1024 * 1024:
                logger.warning("File size exceeded")
                return False
                
            img = self._process_image(image_file)
            results = self.detection_model.predict(
                source=img,
                conf=0.7,
                verbose=False
            )
            
            # Implementasi logika deteksi dan verifikasi
            for result in results:
                if result.boxes:
                    # Ambil embedding wajah terdeteksi
                    x1, y1, x2, y2 = map(int, result.boxes.xyxy[0].tolist())
                    face_img = img[y1:y2, x1:x2]
                    
                    # Dapatkan embedding
                    current_embedding = self._get_embedding(face_img)
                    if current_embedding is None:
                        continue
                    
                    # Bandingkan dengan embedding user
                    similarity = cosine_similarity(
                        [current_embedding],
                        [user.siswa.face_embedding]
                    )
                    return similarity[0][0] > self.similarity_threshold
            return False
            
        except Exception as e:
            logger.error(f"Verification error: {str(e)}", exc_info=True)
            return False

# Singleton instance
face_verifier = FaceVerifier()