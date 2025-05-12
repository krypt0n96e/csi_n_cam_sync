#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Chương trình hiển thị video .avi và đồ thị biên độ CSI theo thời gian thực cho 3 thiết bị (MAC).
Cho phép chọn thư mục chứa video trước khi nhảy đến timestamp để đồng bộ.
Đồ thị gồm 2 cột: cột 1 heatmap biên độ trên các subcarrier, cột 2 line plot biên độ trung bình theo thời gian.
Cửa sổ thời gian ±1s quanh timestamp hiện tại (ms).
Nhãn lấy từ ‘timestamp.csv’ nếu có cột 'start_utc_ms' và 'end_utc_ms', hiển thị trên khung video.
Input CSI file: 'input.csv' với cột 'mac', 'timestamp_real_ms', 'CSI'.
Chỉ giữ các subcarriers sau lọc.
"""
import sys
import os
import cv2
import numpy as np
import pandas as pd
from PyQt5 import QtWidgets, QtCore, QtGui
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

WINDOW_MS = 2000  # ±1s = 1000ms mỗi bên
DEFAULT_FPS = 30

# Hàm lọc CSI raw
def filter_csi_raw(raw_list, null_subcarriers=None):
    sub_ids = list(range(0,1)) + list(range(0,32)) + list(range(-31,0))
    if null_subcarriers is None:
        null_subcarriers = [-31, -30, -29, 0, 28, 29, 30, 31]
    remove_set = set(null_subcarriers)
    filtered = []
    for idx, sc in enumerate(sub_ids):
        if sc in remove_set:
            continue
        filtered.extend([raw_list[2*idx], raw_list[2*idx + 1]])
    return filtered

class MplCanvas(FigureCanvas):
    def __init__(self, parent=None, width=8, height=6, dpi=100, nrows=3, ncols=2):
        self.fig = Figure(figsize=(width, height), dpi=dpi)
        self.axes = [[self.fig.add_subplot(nrows, ncols, i*ncols + j + 1)
                      for j in range(ncols)] for i in range(nrows)]
        super().__init__(self.fig)
        self.fig.tight_layout()

class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("CSI Amplitude & Heatmap Viewer")
        # Folder chứa video & dữ liệu
        self.folder_path = None
        self.cap = None
        self.video_start = None
        self.video_end = None
        self.current_ts = None
        self.current_label = ''
        self.current_location = ''
        # Đọc nhãn (timestamp.csv)
        self.labels_df = None
        # Đọc CSI (input.csv)
        self.csi_df = None
        self.mac_list = []
        # Widgets
        self.folderButton = QtWidgets.QPushButton('Chọn thư mục')
        self.folderButton.clicked.connect(self.choose_folder)
        self.lineEdit = QtWidgets.QLineEdit(placeholderText='Nhập timestamp (ms)')
        self.jumpButton = QtWidgets.QPushButton('Jump')
        self.jumpButton.clicked.connect(self.on_jump)
        self.playButton = QtWidgets.QPushButton('Play')
        self.playButton.clicked.connect(self.on_play)
        self.slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.slider.setEnabled(False)
        self.slider.valueChanged.connect(self.on_slider_change)
        self.videoLabel = QtWidgets.QLabel()
        self.videoLabel.setFixedSize(640, 480)
        self.videoLabel.setStyleSheet('background-color:black;')
        self.canvas = MplCanvas(self)
        # Layout
        ctrl = QtWidgets.QHBoxLayout()
        ctrl.addWidget(self.folderButton)
        ctrl.addWidget(QtWidgets.QLabel('Timestamp (ms):'))
        ctrl.addWidget(self.lineEdit)
        ctrl.addWidget(self.jumpButton)
        ctrl.addWidget(self.playButton)
        ctrl.addWidget(self.slider)
        top = QtWidgets.QHBoxLayout()
        top.addWidget(self.videoLabel)
        top.addWidget(self.canvas)
        mb = QtWidgets.QVBoxLayout()
        mb.addLayout(top)
        mb.addLayout(ctrl)
        w = QtWidgets.QWidget()
        w.setLayout(mb)
        self.setCentralWidget(w)
        # Timer
        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self.next_frame)
        self.timer.setInterval(int(1000/DEFAULT_FPS))
        self.isPlaying = False

    def choose_folder(self):
        folder = QtWidgets.QFileDialog.getExistingDirectory(self, 'Chọn thư mục chứa video và CSV', os.getcwd())
        if not folder:
            return
        self.folder_path = folder
        # Load CSV
        csv_ts = os.path.join(folder, 'timestamps.csv')
        if os.path.exists(csv_ts):
            df = pd.read_csv(csv_ts)
            if 'start_utc_ms' in df.columns and 'end_utc_ms' in df.columns:
                self.labels_df = df
        csi_path = os.path.join(folder, 'csi_data_20250508_101047_snapped_forward.csv')
        if os.path.exists(csi_path):
            self.csi_df = pd.read_csv(csi_path, usecols=['mac', 'timestamp_real_ms', 'CSI'])
            self.mac_list = self.csi_df['mac'].unique()[:3].tolist()
        # Reset video
        if self.cap:
            self.cap.release()
            self.cap = None
        self.slider.setEnabled(False)
        self.videoLabel.clear()

    def find_video_file(self, ts):
        # Tìm file .avi trong thư mục có start <= ts
        files = [f for f in os.listdir(self.folder_path) if f.lower().endswith('.avi')]
        starts = []
        for f in files:
            name = os.path.splitext(f)[0]
            if name.isdigit():
                starts.append(int(name))
        if not starts:
            return None
        # Lấy start lớn nhất <= ts, nếu không có thì nhỏ nhất
        cand = [s for s in starts if s <= ts]
        if cand:
            chosen = max(cand)
        else:
            chosen = min(starts)
        return os.path.join(self.folder_path, f"{chosen}.avi"), chosen

    def on_jump(self):
        if not self.folder_path:
            QtWidgets.QMessageBox.warning(self, 'Lỗi', 'Chưa chọn thư mục chứa video!')
            return
        try:
            ts = int(self.lineEdit.text())
        except ValueError:
            QtWidgets.QMessageBox.warning(self, 'Lỗi', 'Timestamp không hợp lệ!')
            return
        # Load video lần đầu và label
        if self.cap is None:
            # Tìm file video và video_start
            result = self.find_video_file(ts)
            if not result:
                QtWidgets.QMessageBox.critical(self, 'Lỗi', 'Không có file video .avi trong thư mục!')
                return
            video_file, vs = result
            self.video_start = vs
            # Label
            self.current_label = ''
            self.current_location = ''
            if self.labels_df is not None:
                row = self.labels_df[(self.labels_df['start_utc_ms'] <= ts) & (self.labels_df['end_utc_ms'] >= ts)]
                if not row.empty:
                    r = row.iloc[0]
                    self.current_label = str(r.get('label', ''))
                    self.current_location = str(r.get('location', ''))
            # Open video
            self.cap = cv2.VideoCapture(video_file)
            fps = self.cap.get(cv2.CAP_PROP_FPS) or DEFAULT_FPS
            self.timer.setInterval(int(1000/fps))
            frame_count = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
            duration = int(frame_count/fps*1000)
            self.video_end = self.video_start + duration
            # Slider
            self.slider.setEnabled(True)
            self.slider.setMinimum(0)
            self.slider.setMaximum(duration)
        # Tính rel và move
        rel = max(0, min(ts - self.video_start, self.slider.maximum()))
        self.slider.setValue(rel)
        self.current_ts = self.video_start + rel
        self.update_video_frame()
        self.update_plots()

    def on_play(self):
        if not self.cap:
            QtWidgets.QMessageBox.information(self, 'Thông báo', 'Chưa chọn hoặc load video!')
            return
        self.isPlaying = not self.isPlaying
        if self.isPlaying:
            self.timer.start()
        else:
            self.timer.stop()

    def on_slider_change(self, rel):
        self.current_ts = self.video_start + rel
        self.update_video_frame()
        self.update_plots()

    def next_frame(self):
        fps = self.cap.get(cv2.CAP_PROP_FPS) or DEFAULT_FPS
        step = int(1000/fps)
        nr = self.slider.value() + step
        if nr > self.slider.maximum():
            self.timer.stop()
            self.isPlaying = False
            return
        self.slider.setValue(nr)

    def update_video_frame(self):
        rel = self.current_ts - self.video_start
        fps = self.cap.get(cv2.CAP_PROP_FPS) or DEFAULT_FPS
        idx = int(round(rel * fps / 1000))
        total = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if idx < 0 or idx >= total:
            return
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        ret, frame = self.cap.read()
        if not ret:
            return
        # Overlay label, location, timestamp
        text = f"{self.current_label} @ {self.current_location} | t={self.current_ts}ms"
        cv2.putText(frame, text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
        img = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, _ = img.shape
        qimg = QtGui.QImage(img.data, w, h, 3*w, QtGui.QImage.Format_RGB888)
        pix = QtGui.QPixmap.fromImage(qimg)
        self.videoLabel.setPixmap(pix.scaled(self.videoLabel.size(), QtCore.Qt.KeepAspectRatio))

    def parse_csi(self, s):
        arr = np.fromstring(s.strip('[]'), sep=',', dtype=np.int8)
        return arr[0::2] + 1j*arr[1::2]

    def update_plots(self):
        half = WINDOW_MS//2
        t0, t1 = self.current_ts-half, self.current_ts+half
        for i, mac in enumerate(self.mac_list):
            ax_h, ax_l = self.canvas.axes[i]
            ax_h.clear(); ax_l.clear()
            dfw = self.csi_df[(self.csi_df['mac']==mac) &
                               (self.csi_df['timestamp_real_ms']>=t0) &
                               (self.csi_df['timestamp_real_ms']<=t1)]
            if dfw.empty:
                ax_h.text(0.5, 0.5, 'No data', transform=ax_h.transAxes)
                ax_l.text(0.5, 0.5, 'No data', transform=ax_l.transAxes)
            else:
                raw = [list(map(int, v.strip('[]').split(','))) for v in dfw['CSI']]
                filt = [filter_csi_raw(r) for r in raw]
                amps = [np.abs(np.array(f)).reshape(-1,2).sum(axis=1) for f in filt]
                mat = np.stack(amps)
                ax_h.imshow(mat.T, aspect='auto', cmap='jet', interpolation='nearest', extent=[t0, t1, 0, mat.shape[1]], origin='lower')
                ax_h.axvline(self.current_ts, linestyle='--')
                ax_h.set_ylabel('Subcarrier')
                mean_amp = mat.mean(axis=1)
                ax_l.plot(dfw['timestamp_real_ms'], mean_amp)
                ax_l.axvline(self.current_ts, linestyle='--')
                ax_l.set_ylabel('Amp')
            ax_l.set_xlabel('ms')
        self.canvas.draw()

if __name__=='__main__':
    app = QtWidgets.QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec_())
