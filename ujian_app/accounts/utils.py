import numpy as np
import librosa
import os
from pydub import AudioSegment
from ultralytics import YOLO
import os
from django.core.files.base import ContentFile
from django.conf import settings
from PIL import Image, ImageEnhance
import numpy as np

def preprocess_audio(file_path, target_sr=16000, pre_emphasis_coef=0.97, trim_silence=True):
    # Load audio asli tanpa resample dulu
    y, sr = librosa.load(file_path, sr=None)

    # Resample jika perlu
    if sr != target_sr:
        y = librosa.resample(y, orig_sr=sr, target_sr=target_sr)
        sr = target_sr

    # Stereo ke mono
    if y.ndim > 1:
        y = np.mean(y, axis=1)

    # Normalisasi amplitudo ke [-1, 1]
    y = y / (np.max(np.abs(y)) + 1e-9)

    # Pre-emphasis filter
    y = np.append(y[0], y[1:] - pre_emphasis_coef * y[:-1])

    # Trim silence
    if trim_silence:
        y, _ = librosa.effects.trim(y, top_db=20)

    return y, sr

def extract_mfcc(file_path, n_mfcc=13):
    try:
        # Konversi file (jika perlu) ke wav
        temp_wav = file_path + ".wav_conv"
        AudioSegment.from_file(file_path).export(temp_wav, format="wav")

        # Preprocessing audio
        y, sr = preprocess_audio(temp_wav, target_sr=16000, pre_emphasis_coef=0.97, trim_silence=True)

        # Ekstraksi MFCC
        mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=n_mfcc)

        os.remove(temp_wav)
        return mfcc.T  # transpose supaya frame x fitur
    except Exception as e:
        print(f"[ERROR] extract_mfcc failed: {e}")
        if os.path.exists(temp_wav):
            os.remove(temp_wav)
        return None

# Asumsikan yolo_model sudah ter‐inisialisasi (misalnya di settings atau di atas file ini)
yolo_model = YOLO(settings.YOLO_FACE_MODEL)

def preprocess_face_image(uploaded_image_file):
    # 1. Buka dan verifikasi
    img = Image.open(uploaded_image_file)
    img.verify()
    uploaded_image_file.seek(0)
    img = Image.open(uploaded_image_file).convert('RGB')
    img_array = np.array(img)

    # 2. Deteksi wajah dengan YOLO
    results = yolo_model(img_array)[0]
    boxes = results.boxes.xyxy.cpu().numpy()
    if len(boxes) == 0:
        raise ValueError("Wajah tidak terdeteksi oleh YOLO.")

    # 3. Ambil bounding‐box pertama, potong (crop)
    x1, y1, x2, y2 = boxes[0][:4].astype(int)
    top = max(0, y1)
    right = min(img_array.shape[1], x2)
    bottom = min(img_array.shape[0], y2)
    left = max(0, x1)
    face_crop = img.crop((left, top, right, bottom))  # PIL menggunakan (left, top, right, bottom)

    return face_crop  


def augment_face_images(face_img: Image.Image):
    augmented_list = []

    # 1. Original
    augmented_list.append(face_img.copy())

    # 2. Horizontal flip
    flip = face_img.transpose(Image.FLIP_LEFT_RIGHT)
    augmented_list.append(flip)

    # 3. Rotasi +15°
    rot_plus = face_img.rotate(15, expand=True)
    augmented_list.append(rot_plus)

    # 4. Rotasi -15°
    rot_minus = face_img.rotate(-15, expand=True)
    augmented_list.append(rot_minus)

    # 5. Brightness +20%
    enhancer = ImageEnhance.Brightness(face_img)
    bright_plus = enhancer.enhance(1.2)
    augmented_list.append(bright_plus)

    # 6. Brightness -20%
    bright_minus = enhancer.enhance(0.8)
    augmented_list.append(bright_minus)

    return augmented_list