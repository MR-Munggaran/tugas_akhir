// static/js/ujian.js

// Variabel global dari template
let ujianId = null;
let totalSoal = 0;
let waktuHabis = null;
let csrfToken = null;

function initVariables() {
    ujianId = document.getElementById('ujian-container').dataset.ujianId;
    totalSoal = parseInt(document.getElementById('ujian-container').dataset.totalSoal);
    waktuHabis = new Date(document.getElementById('timer').dataset.waktuHabis);
    csrfToken = document.querySelector('[name=csrfmiddlewaretoken]').value;
}

// Fungsi navigasi soal
function confirmSubmit() {
    return confirm('Apakah Anda yakin sudah menyelesaikan semua soal?');
}

function nextSoal() {
    if (currentSoal < totalSoal) {
        showSoal(currentSoal + 1);
    }
}

// Inisialisasi tampilan
function initUI() {
    // Sembunyikan semua soal kecuali pertama
    document.querySelectorAll('.soal-container').forEach((soal, index) => {
        if (index !== 0) soal.style.display = 'none';
    });

    // Atur tampilan tombol Next awal
    document.querySelectorAll('.next-btn').forEach((btn, index) => {
        btn.style.display = (index === 0 && totalSoal > 1) ? 'block' : 'none';
    });

    // Handle hash URL
    const currentHash = window.location.hash;
    if (currentHash.startsWith('#soal')) {
        const noSoal = parseInt(currentHash.replace('#soal', ''));
        showSoal(noSoal);
    } else {
        showSoal(1);
    }
}

// Fungsi navigasi utama
function handleSoalClick(event, no) {
    event.preventDefault();
    showSoal(parseInt(no));
}

function showSoal(no) {
    // Validasi nomor soal
    if (no < 1 || no > totalSoal) return;

    // Update currentSoal
    currentSoal = no;

    // Sembunyikan semua soal
    document.querySelectorAll('.soal-container').forEach(soal => {
        soal.style.display = 'none';
    });

    // Tampilkan soal target
    const targetSoal = document.getElementById(`soal${no}`);
    if (targetSoal) {
        targetSoal.style.display = 'block';
        
        // Update navigasi samping
        document.querySelectorAll('.list-group-item').forEach(item => {
            item.classList.remove('active');
        });
        document.querySelector(`a[href="#soal${no}"]`).classList.add('active');
        
        // Update URL hash
        history.replaceState(null, null, `#soal${no}`);
    }

    // Update tombol Next
    document.querySelectorAll('.next-btn').forEach(btn => {
        btn.style.display = (no < totalSoal) ? 'block' : 'none';
    });
}

// Timer countdown
let timerInterval;

function updateTimer() {
    const now = new Date();
    const diff = waktuHabis - now;
    
    if (diff <= 0) {
        clearInterval(timerInterval);
        document.getElementById('timer').textContent = "Waktu Habis!";
        document.getElementById('ujianForm').submit();
        return;
    }
    
    const hours = Math.floor(diff / 3600000);
    const minutes = Math.floor((diff % 3600000) / 60000);
    const seconds = Math.floor((diff % 60000) / 1000);
    
    document.getElementById('timer').textContent = 
        `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
    
    if (hours === 0 && minutes < 5) {
        document.querySelector('.timer').classList.replace('bg-danger', 'bg-warning');
    }
}

// Proctoring
let proctoringInterval;

async function startWebcam() {
    try {
        const stream = await navigator.mediaDevices.getUserMedia({ video: true });
        document.getElementById('webcam').srcObject = stream;
    } catch (error) {
        alert('Tidak dapat mengakses kamera. Pastikan izin kamera diberikan.');
    }
}

function captureAndSend() {
    const video = document.getElementById('webcam');
    const canvas = document.createElement('canvas');
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    canvas.getContext('2d').drawImage(video, 0, 0);

    canvas.toBlob(blob => {
        const formData = new FormData();
        formData.append('image', blob, 'webcam.jpg');

        fetch(`/proctoring/${ujianId}/`, {
            method: 'POST',
            headers: { 'X-CSRFToken': csrfToken },
            body: formData
        })
        .then(response => response.json())
        .then(data => {
            const statusDiv = document.getElementById('proctoring-status');
            if (data.event_type === 'MISS_MATCH') {
                statusDiv.innerHTML = '<span class="text-danger">Wajah tidak cocok!</span>';
            } else {
                statusDiv.innerHTML = '<span class="text-success">Verifikasi OK</span>';
            }
        })
        .catch(error => {
            console.error('Proctoring error:', error);
            statusDiv.innerHTML = '<span class="text-warning">Error verifikasi</span>';
        });
    }, 'image/jpeg', 0.7);
}

// Inisialisasi
document.addEventListener('DOMContentLoaded', () => {
    initVariables();
    initUI();
    startWebcam();
    proctoringInterval = setInterval(captureAndSend, 30000);
    timerInterval = setInterval(updateTimer, 1000);
    updateTimer();
    
    // Prevent page leave
    window.addEventListener('beforeunload', (e) => {
        if (document.getElementById('timer').textContent !== "Waktu Habis!") {
            e.preventDefault();
            e.returnValue = '';
        }
    });
});