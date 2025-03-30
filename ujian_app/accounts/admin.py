from django.contrib import admin
from .models import User, Guru, Siswa

@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('username', 'email', 'is_guru', 'is_siswa')

@admin.register(Guru)
class GuruAdmin(admin.ModelAdmin):
    list_display = ('user', 'nama_lengkap')

@admin.register(Siswa)
class SiswaAdmin(admin.ModelAdmin):
    list_display = ('user', 'nama_lengkap')