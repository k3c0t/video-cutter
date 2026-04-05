Professional AI Video Auto-Cutter

NCOTS Studio adalah aplikasi desktop *video editing* otomatis berbasis **Python & PySide6** yang didesain khusus untuk *content creator* dan agensi sosial media. Aplikasi ini dapat memotong video secara presisi dan mengubahnya ke berbagai rasio layar (YouTube, TikTok, Instagram) secara bersamaan (*Batch Processing*), lengkap dengan integrasi AI Generatif untuk pembuatan *background* otomatis.

## ✨ Fitur Unggulan

- **Smart Batch Processing:** Potong satu video dan *render* ke 5 format rasio layar berbeda (9:16, 16:9, 1:1, 5:7, 3:4) dalam sekali klik.
- **OpenAI DALL-E 3 Integration:** Mode khusus *Podcast* (9:16) yang dapat secara otomatis memanggil API OpenAI untuk membuat dan menempelkan *background* hasil AI (DALL-E 3) agar video lanskap (16:9) tidak terpotong di kiri-kanannya.
- **Auto-Fallback System:** Jika API Key OpenAI kosong, salah, atau limit habis, sistem akan secara cerdas beralih menggunakan efek sinematik *Background Blur* agar proses *render* tidak *crash* atau gagal.
- **Eco-Mode & Anti-Crash:** Dibangun menggunakan `subprocess.Popen` dengan *CPU Limiter* (`-threads 4`) untuk mencegah komputer *overheat*. Dilengkapi sensor *Kill-Switch* yang akan langsung menghentikan paksa mesin pemroses (FFmpeg) saat aplikasi ditutup.
- **Professional UI/UX:** Antarmuka bergaya *Dark Mode* 2-Kolom yang ramping, responsif, dan elegan, dilengkapi Terminal Log bawaan untuk memantau progres *render* dan mendeteksi pesan *error* secara *real-time*.

---


## 📖 Cara Penggunaan

### 🎛️ Panel Kiri (Setup & Pengaturan)
* **Source Media:** Pilih video sumber (`.mp4`) yang ingin dipotong.
* **Durasi Potongan:** Masukkan waktu mulai dan akhir. Program mendukung format angka detik tunggal (contoh: `15`) atau format jam standar (contoh: `01:15` atau `01:15:20`).
* **Aspect Ratio:** Centang rasio layar target. Anda bisa mencentang lebih dari satu opsi untuk melakukan *batch rendering* secara bersamaan.
* **AI & Branding:** * Masukkan **API Key OpenAI** dan tulis **DALL-E Prompt** dalam bahasa Inggris jika Anda memilih opsi layar `9:16 (Podcast DALL-E / Blur)`.
  * Pilih gambar `.png` transparan untuk menyematkan **Watermark** (logo akan otomatis diposisikan di pojok kiri bawah dengan jarak aman).

### 🚀 Panel Kanan (Eksekusi)
1. **Output Settings:** Tentukan nama dasar file hasil (contoh: `podcast_eps1.mp4`). Sistem akan otomatis menambahkan label resolusi di nama file akhirnya (contoh: `podcast_eps1_9x16_Podcast.mp4`).
2. Klik tombol biru **🚀 START BATCH RENDER**.
3. Pantau seluruh alur proses *download* gambar AI dan kompresi video melalui **Live Process Terminal** di bagian bawah layar.

---

## ⚙️ Arsitektur Core (Under the Hood)

* **GUI Framework:** Menggunakan `PySide6` untuk *rendering* UI berbasis komponen (Qt). Tampilan diformat ulang secara menyeluruh dengan CSS khusus agar menyamai *software editing* PC komersial kelas atas.
* **Multi-Threading (`QThread`):** Menjalankan *instance* mesin `RenderWorker` di latar belakang secara asinkronus, sehingga *User Interface* tidak mengalami *freeze* (Not Responding) selama proses *rendering* video yang berat.
* **Terminal Redirector:** Membajak jalur komunikasi *stdout* (`print`) bawaan Python dan meneruskannya secara asinkron ke elemen `QTextEdit` GUI menggunakan arsitektur `Signal` dan `Slot`.
* **FFmpeg Filter Logic:** Berfungsi sebagai jantung pemrosesan visual. Memanfaatkan `imageio-ffmpeg` untuk memanipulasi `filter_complex` berlapis yang menggabungkan: Video asli, *Background* AI, *Scaling* dinamis, Teks/Gambar Watermark, dan pemetaan Audio murni ke dalam satu perintah CLI komprehensif.

---

## ⚠️ Disclaimer

> **Catatan Penting:**
> * Pastikan Anda **tidak mengekspos API Key OpenAI** rahasia Anda ke publik (misalnya tanpa sengaja mengunggahnya ke repositori GitHub).
> * Penggunaan API DALL-E 3 akan **memotong saldo kredit** di akun OpenAI Anda sesuai dengan tarif resmi yang berlaku. 
> * Jika Anda tidak ingin menggunakan fitur berbayar ini, cukup **kosongkan kolom API Key** pada aplikasi. Sistem akan secara otomatis beralih menggunakan efek *Background Blur* bawaan secara gratis.
