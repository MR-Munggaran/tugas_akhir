from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
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
    nama_lengkap = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Masukkan nama lengkap'})
    )
    kelas = forms.ModelChoiceField(
        queryset=Kelas.objects.all(),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    class Meta:
        model = User
        fields = ('username', 'email', 'password1', 'password2', 'nama_lengkap', 'kelas')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Menambahkan class 'form-control' ke field bawaan UserCreationForm
        self.fields['username'].widget.attrs.update({'class': 'form-control', 'placeholder': 'Masukkan username'})
        self.fields['email'].widget.attrs.update({'class': 'form-control', 'placeholder': 'Masukkan email'})
        self.fields['password1'].widget.attrs.update({'class': 'form-control', 'placeholder': 'Masukkan password'})
        self.fields['password2'].widget.attrs.update({'class': 'form-control', 'placeholder': 'Konfirmasi password'})

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
        fields = ['nama_ujian', 'deskripsi', 'durasi_menit', 'waktu_mulai', 'waktu_selesai']
        widgets = {
            'nama_ujian': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Masukkan nama ujian'
            }),
            'deskripsi': forms.Textarea(attrs={
                'class': 'form-control',
                'placeholder': 'Masukkan deskripsi ujian',
                'rows': 3
            }),
            'durasi_menit': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Masukkan durasi dalam menit'
            }),
            'waktu_mulai': forms.DateTimeInput(attrs={
                'class': 'form-control',
                'type': 'datetime-local'
            }),
            'waktu_selesai': forms.DateTimeInput(attrs={
                'class': 'form-control',
                'type': 'datetime-local'
            }),
        }

class SoalForm(forms.ModelForm):
    class Meta:
        model = Soal
        fields = ['pertanyaan', 'pilihan_a', 'pilihan_b', 'pilihan_c', 'pilihan_d', 'jawaban_benar']
        widgets = {
            'pertanyaan': forms.Textarea(attrs={
                'class': 'form-control',
                'placeholder': 'Masukkan pertanyaan',
                'rows': 3
            }),
            'pilihan_a': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Pilihan A'
            }),
            'pilihan_b': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Pilihan B'
            }),
            'pilihan_c': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Pilihan C'
            }),
            'pilihan_d': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Pilihan D'
            }),
            'jawaban_benar': forms.Select(attrs={
                'class': 'form-select'
            }),
        }