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

class VoiceModelForm(forms.ModelForm):
    class Meta:
        model = Siswa
        fields = ['voice_model']
        widgets = {
            'voice_model': forms.FileInput(attrs={'accept': '.joblib'})
        }

class SiswaForm(forms.ModelForm):
    class Meta:
        model = Siswa
        fields = ['nama_lengkap', 'kelas']

class SiswaCreationForm(UserCreationForm):
    nama_lengkap = forms.CharField(  # Pindahkan ke sini
        max_length=100,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Masukkan nama lengkap'})
    )
    kelas = forms.ModelChoiceField(  # Pindahkan ke sini
        queryset=Kelas.objects.all(),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    class Meta:
        model = User
        fields = ('username', 'email', 'password1', 'password2')  # Hapus nama_lengkap dan kelas

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

class UserEditForm(forms.ModelForm):
    new_password = forms.CharField(
        label="Password Baru",
        widget=forms.PasswordInput(attrs={'autocomplete': 'new-password', 'class': 'form-control',}),
        required=False,
        help_text="Kosongkan jika tidak ingin mengganti password"
    )
    confirm_password = forms.CharField(
        label="Konfirmasi Password",
        widget=forms.PasswordInput(attrs={'autocomplete': 'new-password', 'class': 'form-control',}),
        required=False
    )

    class Meta:
        model = User
        fields = ['username', 'email']
        required = False
        labels = {
            'username': 'Username',
            'email': 'Email'
        }
        widgets = {
            'username': forms.TextInput(attrs={'placeholder': 'Username Anda', 'class': 'form-control',}),
            'email': forms.EmailInput(attrs={'placeholder': 'Alamat email Anda', 'class': 'form-control',})
        }

    def clean(self):
        cleaned_data = super().clean()
        new_password = cleaned_data.get("new_password")
        confirm_password = cleaned_data.get("confirm_password")

        if new_password or confirm_password:
            if new_password != confirm_password:
                self.add_error('confirm_password', "Password tidak cocok")
        return cleaned_data

class ProfileEditForm(forms.ModelForm):
    class Meta:
        fields = ['nama_lengkap']
        labels = {'nama_lengkap': 'Nama Lengkap'}
        widgets = {
            'nama_lengkap': forms.TextInput(attrs={'placeholder': 'Nama lengkap Anda', 'class': 'form-control',})
        }

class GuruProfileForm(ProfileEditForm):
    class Meta(ProfileEditForm.Meta):
        model = Guru

class SiswaProfileForm(ProfileEditForm):
    class Meta(ProfileEditForm.Meta):
        model = Siswa