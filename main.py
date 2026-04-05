import sys
import os
import subprocess
import gc
import urllib.request
import urllib.parse
import urllib.error
import json
import imageio_ffmpeg
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                               QHBoxLayout, QPushButton, QLabel, QLineEdit, 
                               QCheckBox, QFileDialog, QTextEdit, QGroupBox, QMessageBox, QGridLayout)
from PySide6.QtCore import Qt, QThread, Signal, QObject
from PySide6.QtGui import QTextCursor, QFont

def parse_time(waktu_str):
    try:
        parts = str(waktu_str).strip().split(':')
        if len(parts) == 1: return float(parts[0])
        elif len(parts) == 2: return float(parts[0]) * 60 + float(parts[1])
        elif len(parts) == 3: return float(parts[0]) * 3600 + float(parts[1]) * 60 + float(parts[2])
    except ValueError:
        pass
    return 0.0

class EmittingStream(QObject):
    textWritten = Signal(str)
    def write(self, text):
        self.textWritten.emit(str(text))
    def flush(self): pass

# =======================================================
# CLASS WORKER: ENGINE FFMPEG (LOGIKA TETAP SAMA 100%)
# =======================================================
class RenderWorker(QThread):
    finished = Signal(bool)

    def __init__(self, input_path, base_output, start_time, end_time, list_format, watermark_path=None, ai_prompt=None, api_key=None):
        super().__init__()
        self.input_path = input_path
        self.base_output = base_output
        self.start_time = start_time
        self.end_time = end_time
        self.list_format = list_format
        self.watermark_path = watermark_path
        self.ai_prompt = ai_prompt
        self.api_key = api_key
        
        self.process = None       
        self.is_cancelled = False 

    def batalkan_proses(self):
        self.is_cancelled = True
        if self.process:
            try: self.process.kill() 
            except: pass

    def download_openai_background(self, prompt, output_path):
        print(f"\n[AI] Memanggil OpenAI (DALL-E 3) untuk: '{prompt}' ...")
        if not self.api_key:
            print("[AI] ⚠️ API Key OpenAI kosong! Mengalihkan ke efek Blur...")
            return False

        url = "https://api.openai.com/v1/images/generations"
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {self.api_key}"}
        data = {"model": "dall-e-3", "prompt": prompt, "n": 1, "size": "1024x1792"}
        
        req = urllib.request.Request(url, data=json.dumps(data).encode('utf-8'), headers=headers, method='POST')

        try:
            with urllib.request.urlopen(req) as response:
                res_data = json.loads(response.read().decode('utf-8'))
                image_url = res_data['data'][0]['url']
                
            print("[AI] ⏳ Mengunduh gambar kualitas HD dari server OpenAI...")
            req_img = urllib.request.Request(image_url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req_img) as response_img:
                with open(output_path, 'wb') as out_file:
                    out_file.write(response_img.read())
            print("[AI] ✅ Background DALL-E 3 berhasil diamankan!")
            return True
            
        except urllib.error.HTTPError as e:
            error_info = e.read().decode('utf-8')
            print(f"[AI] ❌ OpenAI Error ({e.code}): {error_info}")
            print("[AI] ⚠️ Mengalihkan ke efek Blur Background...")
            return False
        except Exception as e:
            print(f"[AI] ❌ Gagal koneksi: {e}. Mengalihkan ke efek Blur...")
            return False

    def run(self):
        durasi = self.end_time - self.start_time
        if durasi <= 0:
            print("\n[-] Error: Waktu akhir harus lebih besar dari waktu mulai!")
            self.finished.emit(False)
            return

        ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
        semua_sukses = True
        temp_ai_bg = os.path.join(os.path.dirname(self.base_output), "temp_openai_bg.jpg")

        print(f"\n[*] MEMULAI BATCH RENDER: {len(self.list_format)} Format Video")
        print("="*60)

        for idx, format_kode in enumerate(self.list_format, start=1):
            if self.is_cancelled:
                print("\n[!] PROSES DIBATALKAN PAKSA OLEH SISTEM.")
                break

            is_podcast_format = (format_kode == '6')
            if format_kode == '1':
                suffix, tipe = "_9x16_CenterCrop", "Vertikal 9:16 (Center Crop)"
                vf_filter = "crop='min(iw,ih*9/16)':'ih':'(iw-min(iw,ih*9/16))/2':0,scale=1080:1920"
            elif format_kode == '2':
                suffix, tipe = "_16x9", "Lanskap 16:9"
                vf_filter = "crop='iw':'min(ih,iw*9/16)':0:'(ih-min(ih,iw*9/16))/2',scale=1920:1080"
            elif format_kode == '3':
                suffix, tipe = "_1x1", "Persegi 1:1"
                vf_filter = "crop='min(iw,ih)':'min(iw,ih)':'(iw-min(iw,ih))/2':'(ih-min(iw,ih))/2',scale=1080:1080"
            elif format_kode == '4':
                suffix, tipe = "_5x7", "Cinematic 5:7"
                vf_filter = "crop='min(iw,ih*5/7)':'min(ih,iw*7/5)':'(iw-min(iw,ih*5/7))/2':'(ih-min(ih,iw*7/5))/2',scale=1080:1512"
            elif format_kode == '5':
                suffix, tipe = "_3x4", "IG Standard 3:4"
                vf_filter = "crop='min(iw,ih*3/4)':'min(iw,ih*4/3)':'(iw-min(iw,ih*3/4))/2':'(ih-min(ih,iw*4/3))/2',scale=1080:1440"
            elif is_podcast_format:
                suffix, tipe = "_9x16_Podcast", "Vertikal 9:16 (Podcast Mode)"

            name_part, ext_part = os.path.splitext(self.base_output)
            out_path = f"{name_part}{suffix}{ext_part}"

            print(f"\n[{idx}/{len(self.list_format)}] Merender Format: {tipe}...")
            
            inputs = ['-ss', str(self.start_time), '-i', self.input_path]
            input_counter = 1
            idx_ai = -1
            idx_wm = -1
            
            if is_podcast_format and self.ai_prompt:
                if self.download_openai_background(self.ai_prompt, temp_ai_bg):
                    inputs.extend(['-i', temp_ai_bg])
                    idx_ai = input_counter
                    input_counter += 1

            if self.watermark_path and os.path.exists(self.watermark_path):
                inputs.extend(['-i', self.watermark_path])
                idx_wm = input_counter
                input_counter += 1
            
            if is_podcast_format:
                if idx_ai != -1:
                    current_chain = f"[{idx_ai}:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920[bg];"
                else:
                    current_chain = "[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,boxblur=12:12[bg];"
                
                current_chain += "[0:v]scale=1080:1920:force_original_aspect_ratio=decrease[fg];"
                current_chain += "[bg][fg]overlay=(W-w)/2:(H-h)/2[vid]"
                last_node = "[vid]"

                if idx_wm != -1:
                    current_chain += f";{last_node}[{idx_wm}:v]overlay=30:H-h-30[final_ov]"
                    last_node = "[final_ov]"

                video_args = ['-filter_complex', current_chain, '-map', last_node, '-map', '0:a?']

            else:
                if idx_wm != -1:
                    filter_str = f"[0:v]{vf_filter}[bg_crop];[bg_crop][{idx_wm}:v]overlay=30:H-h-30[final_ov]"
                    video_args = ['-filter_complex', filter_str, '-map', '[final_ov]', '-map', '0:a?']
                else:
                    video_args = ['-vf', vf_filter] 

            cmd = [ffmpeg_exe, '-y'] + inputs + ['-t', str(durasi)] + video_args + [
                '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '23', 
                '-threads', '4', '-c:a', 'aac', '-b:a', '192k', out_path
            ]

            try:
                self.process = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True, encoding='utf-8', errors='replace')
                _, stderr_output = self.process.communicate() 
                
                if self.is_cancelled:
                    semua_sukses = False
                    break
                    
                if self.process.returncode != 0:
                     print(f"\n[!] LOG ERROR FFMPEG:\n{stderr_output}")
                     raise Exception("Render gagal.")
                     
                gc.collect() 
                print(f"   ✅ Selesai: {os.path.basename(out_path)}")
            except Exception as e:
                if not self.is_cancelled:
                    print(f"   ❌ Gagal: {e}")
                semua_sukses = False

        if os.path.exists(temp_ai_bg):
            try: os.remove(temp_ai_bg)
            except: pass

        if not self.is_cancelled:
            print("\n" + "="*60)
            print("[*] SEMUA TUGAS BATCH RENDER SELESAI!")
        self.finished.emit(semua_sukses and not self.is_cancelled)


# =======================================================
# CLASS MAIN WINDOW GUI: REDESIGN PROFESIONAL
# =======================================================
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Tukang Potong Video")
        self.resize(1100, 750) # Diperlebar untuk layout 2 kolom
        self.init_ui()
        sys.stdout = EmittingStream()
        sys.stdout.textWritten.connect(self.normalOutputWritten)

    def init_ui(self):
        # Widget Utama & Layout Horizontal (2 Kolom)
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QHBoxLayout(main_widget)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(20)

        # ==========================================
        # KOLOM KIRI: PANEL SETTING (Bobot 60%)
        # ==========================================
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(15)

        # --- 1. VIDEO SOURCE ---
        group_video = QGroupBox("")
        layout_video = QVBoxLayout()
        layout_video.setContentsMargins(20, 30, 20, 20)
        
        row_vid = QHBoxLayout()
        self.input_video = QLineEdit()
        self.input_video.setPlaceholderText("Select source video (.mp4)...")
        btn_browse_video = QPushButton("Browse File")
        btn_browse_video.clicked.connect(self.browse_video)
        row_vid.addWidget(self.input_video)
        row_vid.addWidget(btn_browse_video)
        layout_video.addLayout(row_vid)
        
        row_time = QHBoxLayout()
        row_time.addWidget(QLabel("Start Time (s/mm:ss):"))
        self.input_start = QLineEdit("01:00")
        row_time.addWidget(self.input_start)
        row_time.addSpacing(15)
        row_time.addWidget(QLabel("End Time (s/mm:ss):"))
        self.input_end = QLineEdit("02:00")
        row_time.addWidget(self.input_end)
        layout_video.addLayout(row_time)
        group_video.setLayout(layout_video)
        left_layout.addWidget(group_video)

        # --- 2. BATCH RESOLUTION ---
        group_format = QGroupBox("")
        layout_format = QGridLayout()
        layout_format.setContentsMargins(20, 30, 20, 20)
        layout_format.setVerticalSpacing(15)
        
        self.chk_1 = QCheckBox("9:16 (Center Crop / Solo)")
        self.chk_6 = QCheckBox("9:16 (Podcast DALL-E / Blur)") 
        self.chk_2 = QCheckBox("16:9 (YouTube Widescreen)")
        self.chk_3 = QCheckBox("1:1 (Instagram Feed)")
        self.chk_4 = QCheckBox("5:7 (Cinematic Portrait)")
        self.chk_5 = QCheckBox("3:4 (Standard Portrait)")
        
        self.chk_6.setObjectName("highlight_check") # Tanda khusus di CSS
        self.chk_6.setChecked(True)

        layout_format.addWidget(self.chk_6, 0, 0) # Podcast diutamakan
        layout_format.addWidget(self.chk_1, 0, 1) 
        layout_format.addWidget(self.chk_2, 1, 0)
        layout_format.addWidget(self.chk_3, 1, 1)
        layout_format.addWidget(self.chk_4, 2, 0)
        layout_format.addWidget(self.chk_5, 2, 1)
        group_format.setLayout(layout_format)
        left_layout.addWidget(group_format)

        # --- 3. AI & BRANDING ---
        group_media = QGroupBox("")
        layout_media = QVBoxLayout()
        layout_media.setContentsMargins(20, 30, 20, 20)
        layout_media.setSpacing(15)

        row_key = QHBoxLayout()
        row_key.addWidget(QLabel("OpenAI API:"))
        self.input_key = QLineEdit()
        self.input_key.setEchoMode(QLineEdit.Password) 
        self.input_key.setPlaceholderText("sk-proj-xxxxxxxxxxxxxxxxxxx (Optional)")
        row_key.addWidget(self.input_key)
        layout_media.addLayout(row_key)
        
        row_ai = QHBoxLayout()
        row_ai.addWidget(QLabel("DALL-E Prompt:"))
        self.input_ai = QLineEdit()
        self.input_ai.setPlaceholderText("Describe podcast background (Leave blank for blur)")
        row_ai.addWidget(self.input_ai)
        layout_media.addLayout(row_ai)

        row_wm = QHBoxLayout()
        row_wm.addWidget(QLabel("Watermark:"))
        self.input_wm = QLineEdit()
        self.input_wm.setPlaceholderText("Transparent Logo (.png)")
        btn_browse_wm = QPushButton("Browse")
        btn_browse_wm.setFixedWidth(100)
        btn_browse_wm.clicked.connect(self.browse_wm)
        row_wm.addWidget(self.input_wm)
        row_wm.addWidget(btn_browse_wm)
        layout_media.addLayout(row_wm)
        
        group_media.setLayout(layout_media)
        left_layout.addWidget(group_media)
        
        # Spacer agar panel kiri rapat ke atas
        left_layout.addStretch()


        # ==========================================
        # KOLOM KANAN: RENDER STATION (Bobot 40%)
        # ==========================================
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(15)

        # --- 4. OUTPUT SETTING ---
        group_out = QGroupBox("")
        layout_out = QVBoxLayout()
        layout_out.setContentsMargins(20, 30, 20, 20)
        
        row_save = QHBoxLayout()
        row_save.addWidget(QLabel("Base Name:"))
        self.input_output = QLineEdit("render_output.mp4")
        row_save.addWidget(self.input_output)
        layout_out.addLayout(row_save)
        group_out.setLayout(layout_out)
        right_layout.addWidget(group_out)

        # --- 5. RENDER BUTTON ---
        self.btn_render = QPushButton("🚀 START BATCH RENDER")
        self.btn_render.setObjectName("btn_render_primary") # CSS ID khusus
        self.btn_render.setCursor(Qt.PointingHandCursor)
        self.btn_render.clicked.connect(self.start_render)
        right_layout.addWidget(self.btn_render)

        # --- 6. TERMINAL LOG ---
        group_log = QGroupBox("")
        layout_log = QVBoxLayout()
        layout_log.setContentsMargins(15, 25, 15, 15)
        
        self.console_log = QTextEdit()
        self.console_log.setReadOnly(True)
        self.console_log.setObjectName("terminal_log")
        layout_log.addWidget(self.console_log)
        
        group_log.setLayout(layout_log)
        right_layout.addWidget(group_log)

        # Menggabungkan Kolom Kiri (Stretch 6) & Kanan (Stretch 4)
        main_layout.addWidget(left_panel, 6)
        main_layout.addWidget(right_panel, 4)

    # --- SISA FUNGSI GUI SAMA ---
    def normalOutputWritten(self, text):
        cursor = self.console_log.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertText(text)
        self.console_log.setTextCursor(cursor)
        self.console_log.ensureCursorVisible()

    def browse_video(self):
        file, _ = QFileDialog.getOpenFileName(self, "Pilih Video", "", "Video Files (*.mp4 *.mkv *.avi *.mov)")
        if file: self.input_video.setText(file)

    def browse_wm(self):
        file, _ = QFileDialog.getOpenFileName(self, "Pilih Logo", "", "Image Files (*.png)")
        if file: self.input_wm.setText(file)

    def start_render(self):
        in_path = self.input_video.text().strip()
        if not os.path.exists(in_path):
            QMessageBox.warning(self, "Error", "Pilih video asli terlebih dahulu!")
            return

        out_name = self.input_output.text().strip()
        if not out_name.endswith(".mp4"): out_name += ".mp4"
            
        wm_path = self.input_wm.text().strip()
        if wm_path and not os.path.exists(wm_path): wm_path = None 
        
        ai_prompt = self.input_ai.text().strip()
        api_key = self.input_key.text().strip()

        list_format = []
        if self.chk_1.isChecked(): list_format.append('1')
        if self.chk_2.isChecked(): list_format.append('2')
        if self.chk_3.isChecked(): list_format.append('3')
        if self.chk_4.isChecked(): list_format.append('4')
        if self.chk_5.isChecked(): list_format.append('5')
        if self.chk_6.isChecked(): list_format.append('6')

        if not list_format:
            QMessageBox.warning(self, "Peringatan", "Centang minimal satu format layar!")
            return

        start_sec = parse_time(self.input_start.text())
        end_sec = parse_time(self.input_end.text())

        folder_asal = os.path.dirname(in_path)
        full_out_path = os.path.join(folder_asal, out_name)

        self.btn_render.setEnabled(False)
        self.btn_render.setText("⏳ Processing Engine...")
        self.console_log.clear()

        self.worker = RenderWorker(in_path, full_out_path, start_sec, end_sec, list_format, wm_path, ai_prompt, api_key)
        self.worker.finished.connect(self.on_render_finished)
        self.worker.start()

    def on_render_finished(self, success):
        self.btn_render.setEnabled(True)
        self.btn_render.setText("🚀 START BATCH RENDER")
        if success:
            QMessageBox.information(self, "Selesai!", "Semua video berhasil dirender dengan sukses!")
        
    def closeEvent(self, event):
        if hasattr(self, 'worker') and self.worker.isRunning():
            print("\n[!] MENGHENTIKAN MESIN FFMPEG SECARA PAKSA...")
            self.worker.batalkan_proses()
            self.worker.wait() 
        event.accept() 

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # Memaksa font modern
    font = QFont("Segoe UI", 10)
    app.setFont(font)
    
    # ==========================================
    # CSS PROFESIONAL (ADOBE / DAVINCI STYLE)
    # ==========================================
    pro_stylesheet = """
        /* Latar Belakang Utama Aplikasi */
        QMainWindow, QWidget { 
            background-color: #141414; 
            color: #E0E0E0; 
        }
        
        /* Label Teks Biasa */
        QLabel {
            color: #A0A0A0;
            font-weight: 500;
        }

        /* Desain Kotak Grup (GroupBox) yang Flat & Modern */
        QGroupBox { 
            background-color: #1E1E22; 
            border: 1px solid #2D2D30; 
            border-radius: 8px; 
            margin-top: 15px; 
        }
        QGroupBox::title { 
            subcontrol-origin: margin; 
            subcontrol-position: top left;
            left: 20px; 
            top: -10px; 
            background-color: #141414; /* Menyatu dengan latar belakang app */
            padding: 2px 10px; 
            color: #7B8497; 
            font-weight: bold;
            font-size: 11px;
            letter-spacing: 1px;
            border-radius: 4px;
            border: 1px solid #2D2D30;
        }

        /* Desain Kotak Input Teks (Gaya CapCut PC) */
        QLineEdit { 
            background-color: #0D0D0D; 
            border: 1px solid #333338; 
            padding: 8px 12px; 
            border-radius: 6px; 
            color: #FFFFFF;
            font-size: 13px;
        }
        QLineEdit:focus { 
            border: 1px solid #0078D4; 
            background-color: #141414;
        }

        /* Desain Tombol Standar (Abu-abu Flat) */
        QPushButton { 
            background-color: #2D2D30; 
            color: #E0E0E0;
            border: 1px solid #3E3E42; 
            padding: 8px 15px; 
            border-radius: 6px; 
            font-weight: 600;
        }
        QPushButton:hover { 
            background-color: #3E3E42; 
            border: 1px solid #55555A;
        }
        QPushButton:pressed {
            background-color: #1E1E22;
        }

        /* Desain Tombol Render Utama (Ukuran Besar & Warna Aksen) */
        QPushButton#btn_render_primary {
            background-color: #0078D4;
            color: white;
            font-size: 15px;
            font-weight: bold;
            padding: 16px;
            border-radius: 8px;
            border: none;
            margin-top: 10px;
            margin-bottom: 10px;
        }
        QPushButton#btn_render_primary:hover {
            background-color: #2B88D8;
        }
        QPushButton#btn_render_primary:disabled {
            background-color: #2D2D30;
            color: #7A7A7A;
        }

        /* Desain CheckBox Modern */
        QCheckBox { 
            spacing: 10px; 
            font-size: 13px;
            color: #CCCCCC;
        }
        QCheckBox:hover {
            color: #FFFFFF;
        }
        /* Penanda CheckBox Podcast AI (Warna Biru Terang) */
        QCheckBox#highlight_check {
            color: #4DA8DA;
            font-weight: bold;
        }
        
        /* Desain Terminal Log Layaknya Console Asli */
        QTextEdit#terminal_log { 
            background-color: #0A0A0C; 
            color: #10B981; /* Warna hijau matrix/hacker modern */
            font-family: 'Consolas', 'Courier New', monospace; 
            font-size: 12px; 
            padding: 12px; 
            border: 1px solid #202024;
            border-radius: 6px;
            selection-background-color: #0078D4;
        }
        
        /* Desain Scrollbar */
        QScrollBar:vertical {
            border: none;
            background: #141414;
            width: 10px;
            margin: 0px 0px 0px 0px;
        }
        QScrollBar::handle:vertical {
            background: #3E3E42;
            min-height: 20px;
            border-radius: 5px;
        }
        QScrollBar::handle:vertical:hover {
            background: #55555A;
        }
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
            height: 0px;
        }
    """
    app.setStyleSheet(pro_stylesheet)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
