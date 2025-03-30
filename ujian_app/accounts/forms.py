from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import User, Guru, Siswa, Kelas, Ujian, Soal

class GuruRegistrationForm(UserCreationForm):
    nama_lengkap = forms.CharField(max_length=100)

    class Meta:
        model = User
        fields = ('username', 'email', 'password1', 'password2', 'nama_lengkap')

    def save(self, commit=True):
        user = super().save(commit=False)
        user.is_guru = True
        if commit:
            user.save()
            Guru.objects.create(user=user, nama_lengkap=self.cleaned_data['nama_lengkap'])
        return user

class SiswaForm(forms.ModelForm):
    class Meta:
        model = Siswa
        fields = ['nama_lengkap', 'kelas']

class SiswaCreationForm(UserCreationForm):
    nama_lengkap = forms.CharField(max_length=100)
    kelas = forms.ModelChoiceField(queryset=Kelas.objects.all(), required=False)

    class Meta:
        model = User
        fields = ('username', 'email', 'password1', 'password2', 'nama_lengkap', 'kelas')

    def save(self, commit=True):
        user = super().save(commit=False)
        user.is_siswa = True  # Set user sebagai siswa
        if commit:
            user.save()
            # Buat objek Siswa terkait
            Siswa.objects.create(
                user=user,
                nama_lengkap=self.cleaned_data['nama_lengkap'],
                kelas=self.cleaned_data['kelas']
            )
        return user

class KelasForm(forms.ModelForm):
    class Meta:
        model = Kelas
        fields = ['nama_kelas']

class UjianForm(forms.ModelForm):
    class Meta:
        model = Ujian
        fields = ['nama_ujian', 'deskripsi']

class SoalForm(forms.ModelForm):
    class Meta:
        model = Soal
        fields = ['pertanyaan', 'pilihan_a', 'pilihan_b', 'pilihan_c', 'pilihan_d', 'jawaban_benar']