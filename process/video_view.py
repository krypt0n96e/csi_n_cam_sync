#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Chương trình hiển thị video .avi và đồ thị biên độ CSI theo thời gian thực cho 3 thiết bị (MAC).
Cho phép chọn:
 - Thư mục chứa video (.avi)
 - File nhãn (timestamp.csv/timestamps.csv với cột start_utc_ms, end_utc_ms, label, location)
 - File CSI (CSV với mac, timestamp_real_ms, CSI)
Nhập timestamp (ms) để tua video và đồng bộ tín hiệu.
Đồ thị gồm 2 cột: cột 1 heatmap biên độ, cột 2 line plot biên độ từng subcarrier, 3 hàng tương ứng 3 thiết bị.
"""
import sys
import os
import cv2
import numpy as np
import pandas as pd
from PyQt5 import QtWidgets, QtCore, QtGui
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

WINDOW_MS = 1000
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
        # paths
        self.video_folder = None
        self.labels_df = None
        self.csi_df = None
        self.mac_list = []
        # video state
        self.cap = None
        self.video_start = None
        self.video_end = None
        self.current_ts = None
        self.current_label = ''
        self.current_location = ''
        # Widgets
        self.videoButton = QtWidgets.QPushButton('Chọn thư mục video')
        self.videoButton.clicked.connect(self.select_video_folder)
        self.labelsButton = QtWidgets.QPushButton('Chọn file nhãn')
        self.labelsButton.clicked.connect(self.select_labels_file)
        self.csiButton = QtWidgets.QPushButton('Chọn file CSI')
        self.csiButton.clicked.connect(self.select_csi_file)
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
        ctrl.addWidget(self.videoButton)
        ctrl.addWidget(self.labelsButton)
        ctrl.addWidget(self.csiButton)
        ctrl.addWidget(QtWidgets.QLabel('Timestamp (ms):'))
        ctrl.addWidget(self.lineEdit)
        ctrl.addWidget(self.jumpButton)
        ctrl.addWidget(self.playButton)
        ctrl.addWidget(self.slider)
        top = QtWidgets.QHBoxLayout()
        top.addWidget(self.videoLabel)
        top.addWidget(self.canvas)
        main = QtWidgets.QVBoxLayout()
        main.addLayout(top)
        main.addLayout(ctrl)
        w = QtWidgets.QWidget()
        w.setLayout(main)
        self.setCentralWidget(w)
        # Timer
        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self.next_frame)
        self.timer.setInterval(int(1000/DEFAULT_FPS))
        self.isPlaying = False

    def select_video_folder(self):
        folder = QtWidgets.QFileDialog.getExistingDirectory(self, 'Chọn thư mục chứa video')
        if folder:
            self.video_folder = folder

    def select_labels_file(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, 'Chọn file nhãn', filter='CSV Files (*.csv)')
        if path:
            df = pd.read_csv(path)
            if {'start_utc_ms','end_utc_ms','label','location'}.issubset(df.columns):
                self.labels_df = df
            else:
                QtWidgets.QMessageBox.warning(self, 'Lỗi', 'File nhãn không hợp lệ!')
                self.labels_df = None

    def select_csi_file(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, 'Chọn file CSI', filter='CSV Files (*.csv)')
        if path:
            df = pd.read_csv(path, usecols=['mac','timestamp_real_ms','CSI'])
            self.csi_df = df
            self.mac_list = df['mac'].unique()[:3].tolist()

    def find_video_file(self, ts):
        files = [f for f in os.listdir(self.video_folder) if f.lower().endswith('.avi')]
        starts = [int(os.path.splitext(f)[0]) for f in files if os.path.splitext(f)[0].isdigit()]
        cand = [s for s in starts if s <= ts]
        chosen = max(cand) if cand else min(starts)
        return os.path.join(self.video_folder, f"{chosen}.avi"), chosen

    def on_jump(self):
        if not (self.video_folder and self.csi_df is not None):
            QtWidgets.QMessageBox.warning(self, 'Lỗi', 'Chưa chọn video folder hoặc CSI file!')
            return
        try:
            ts = int(self.lineEdit.text())
        except ValueError:
            QtWidgets.QMessageBox.warning(self, 'Lỗi', 'Timestamp không hợp lệ!')
            return
        if self.cap is None:
            vf, vs = self.find_video_file(ts)
            self.video_start = vs
            self.current_label = ''
            self.current_location = ''
            if self.labels_df is not None:
                row = self.labels_df[(self.labels_df['start_utc_ms'] <= ts) & (self.labels_df['end_utc_ms'] >= ts)]
                if not row.empty:
                    r = row.iloc[0]
                    self.current_label = str(r['label'])
                    self.current_location = str(r['location'])
            self.cap = cv2.VideoCapture(vf)
            fps = self.cap.get(cv2.CAP_PROP_FPS) or DEFAULT_FPS
            self.timer.setInterval(int(1000/fps))
            frame_count = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
            dur = int(frame_count / fps * 1000)
            self.video_end = self.video_start + dur
            self.slider.setEnabled(True)
            self.slider.setRange(0, dur)
        rel = max(0, min(ts - self.video_start, self.slider.maximum()))
        self.slider.setValue(rel)
        self.current_ts = self.video_start + rel
        self.update_video_frame()
        self.update_plots()

    def on_play(self):
        if not self.cap:
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
        step = int(1000 / fps)
        nr = self.slider.value() + step
        if nr > self.slider.maximum():
            self.timer.stop()
            self.isPlaying = False
            return
        self.slider.setValue(nr)
    def update_video_frame(self):
        # Nếu có labels_df, tìm lại label và location theo current_ts
        if self.labels_df is not None:
            row = self.labels_df[
                (self.labels_df['start_utc_ms'] <= self.current_ts) &
                (self.labels_df['end_utc_ms'] >= self.current_ts)
            ]
            if not row.empty:
                r = row.iloc[0]
                label = str(r['label'])
                loc = str(r['location'])
            else:
                label = "-1"
                loc = "-1"
        else:
            label = "-1"
            loc = "-1"

        print(f"Label: {label}, Location: {loc}, Timestamp: {self.current_ts}ms")
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

        # Overlay nhãn và timestamp, dùng label/loc vừa cập nhật
        text = f"{label}@{loc} | t={self.current_ts}ms"
        cv2.putText(frame, text, (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)

        # Chuyển qua QPixmap và hiển thị
        img = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, _ = img.shape
        qimg = QtGui.QImage(img.data, w, h, 3 * w, QtGui.QImage.Format_RGB888)
        pix = QtGui.QPixmap.fromImage(qimg)
        self.videoLabel.setPixmap(pix.scaled(
            self.videoLabel.size(), QtCore.Qt.KeepAspectRatio))

    def parse_csi(self, s):
        arr = np.fromstring(s.strip('[]'), sep=',', dtype=np.int8)
        return arr[0::2] + 1j*arr[1::2]

    def update_plots(self):
        half = WINDOW_MS // 2
        t0, t1 = self.current_ts - half, self.current_ts + half
        for i, mac in enumerate(self.mac_list):
            ax_h, ax_l = self.canvas.axes[i]
            ax_h.clear(); ax_l.clear()
            dfw = self.csi_df[(self.csi_df['mac'] == mac) &
                               (self.csi_df['timestamp_real_ms'] >= t0) &
                               (self.csi_df['timestamp_real_ms'] <= t1)]
            if dfw.empty:
                ax_h.text(0.5, 0.5, 'No data', transform=ax_h.transAxes)
                ax_l.text(0.5, 0.5, 'No data', transform=ax_l.transAxes)
            else:
                raw = [list(map(int, v.strip('[]').split(','))) for v in dfw['CSI']]
                filt = [filter_csi_raw(r) for r in raw]
                amps = np.stack([np.abs(np.array(f)).reshape(-1, 2).sum(axis=1) for f in filt])
                ax_h.imshow(amps.T, aspect='auto', cmap='jet', interpolation='nearest', extent=[t0, t1, 0, amps.shape[1]], origin='lower')
                ax_h.axvline(self.current_ts, linestyle='--')
                ax_h.set_ylabel('Subcarrier')
                times = dfw['timestamp_real_ms'].values
                for sc in range(amps.shape[1]):
                    ax_l.plot(times, amps[:, sc], linewidth=1)
                ax_l.axvline(self.current_ts, linestyle='--')
                ax_l.set_ylabel('Amp')
            ax_l.set_xlabel('ms')
        self.canvas.draw()

if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec_())
