import os
import uuid
from django.db import models
from django.contrib.auth.models import AbstractUser

class User(AbstractUser):
    is_guru = models.BooleanField(default=False)
    is_siswa = models.BooleanField(default=False)

class Guru(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, primary_key=True)
    nama_lengkap = models.CharField(max_length=100)

class Siswa(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, primary_key=True)
    nama_lengkap = models.CharField(max_length=100)
    kelas = models.ForeignKey('Kelas', on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return self.nama_lengkap

class Kelas(models.Model):
    nama_kelas = models.CharField(max_length=100)

    def __str__(self):
        return self.nama_kelas

class LogMasukStudent(models.Model):
    siswa = models.ForeignKey(Siswa, on_delete=models.CASCADE)
    waktu_masuk = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.siswa.nama_lengkap} - {self.waktu_masuk}"
    
class Ujian(models.Model):
    nama_ujian = models.CharField(max_length=100)
    deskripsi = models.TextField(blank=True, null=True)
    tanggal_dibuat = models.DateTimeField(auto_now_add=True)
    guru = models.ForeignKey(User, on_delete=models.CASCADE, related_name='ujian_dibuat')
    code = models.CharField(max_length=10, unique=True, blank=True)
    durasi_menit = models.PositiveIntegerField(default=60)  # Durasi dalam menit
    waktu_mulai = models.DateTimeField(null=True, blank=True)  # Untuk ujian terjadwal
    waktu_selesai = models.DateTimeField(null=True, blank=True)
    
    def save(self, *args, **kwargs):
        if not self.code:
            self.code = str(uuid.uuid4())[:8].upper()
        super().save(*args, **kwargs)
    
    @property
    def durasi_detik(self):
        return self.durasi_menit * 60

class Soal(models.Model):
    ujian = models.ForeignKey(Ujian, on_delete=models.CASCADE, related_name='soal')
    pertanyaan = models.TextField()
    pilihan_a = models.CharField(max_length=200)
    pilihan_b = models.CharField(max_length=200)
    pilihan_c = models.CharField(max_length=200)
    pilihan_d = models.CharField(max_length=200)
    jawaban_benar = models.CharField(max_length=1, choices=[('A', 'A'), ('B', 'B'), ('C', 'C'), ('D', 'D')])

    def __str__(self):
        return self.pertanyaan[:50]  # Menampilkan 50 karakter pertama dari pertanyaan

class HasilUjian(models.Model):
    siswa = models.ForeignKey(User, on_delete=models.CASCADE)
    ujian = models.ForeignKey(Ujian, on_delete=models.CASCADE)
    nilai = models.FloatField()
    tanggal_selesai = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('siswa', 'ujian')  # Satu siswa hanya bisa sekali mengerjakan ujian

    def __str__(self):
        return f"{self.siswa.username} - {self.ujian.nama_ujian} - {self.nilai}"
    
class JawabanSiswa(models.Model):
    siswa = models.ForeignKey(User, on_delete=models.CASCADE)
    soal = models.ForeignKey(Soal, on_delete=models.CASCADE)
    jawaban = models.CharField(max_length=1)
    waktu_jawab = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('siswa', 'soal')  # Satu jawaban per soal per siswa

class ProctoringLog(models.Model):
    EVENT_CHOICES = [
        ('MATCH', 'Match'),
        ('MISS_MATCH', 'Miss Match'),
        ('ERROR', 'Error'),
    ]
    ujian = models.ForeignKey(Ujian, on_delete=models.CASCADE)
    siswa = models.ForeignKey(User, on_delete=models.CASCADE)
    timestamp = models.DateTimeField(auto_now_add=True)
    event_type = models.CharField(max_length=20, choices=EVENT_CHOICES)
    description = models.TextField()

class VoiceData(models.Model):
    user         = models.OneToOneField(User, on_delete=models.CASCADE)
    scaler_model = models.BinaryField(null=True, blank=True)
    gmm_model    = models.BinaryField(null=True, blank=True)
    threshold    = models.FloatField(default=-1000.0)
    margin       = models.FloatField(default=10.0) 
    is_trained   = models.BooleanField(default=False)

    def __str__(self):
        return f"VoiceData for {self.user.username}"

class VoiceSample(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='voice_samples')
    audio_file = models.FileField(upload_to='voice_samples/')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Sample {self.id} for {self.user.username}"

    def delete(self, *args, **kwargs):
        if self.audio_file:
            if os.path.isfile(self.audio_file.path):
                os.remove(self.audio_file.path)
        super().delete(*args, **kwargs)
    
def user_face_path(instance, filename):
    return f'faces/{instance.user.username}/{filename}'

class UserFace(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    encoding = models.BinaryField()
    photo = models.ImageField(upload_to=user_face_path)

    def __str__(self):
        return f"Wajah {self.user.username}"
    
class AugmentedFace(models.Model):
    user_face = models.ForeignKey(
        UserFace,
        on_delete=models.CASCADE,
        related_name="augmented_images"
    )
    # Kita hanya perlu field ImageField untuk menyimpan gambar augmentasi
    image = models.ImageField(upload_to=user_face_path)
    # (Optional) Anda bisa tambahkan field extra, misalnya tipe augmentasi,
    # timestamp, atau encoding baru jika ingin.
    augment_type = models.CharField(max_length=50, blank=True, null=True)

    def __str__(self):
        return f"Augmentasi {self.augment_type or '–'} untuk {self.user_face.user.username}"

class FaceTestImage(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='face_test_images')
    image = models.ImageField(upload_to='face_tests/%Y/%m/%d/')
    encoding = models.BinaryField(null=True, blank=True)  # simpan encoding wajah dalam bytes
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.image.name}"
