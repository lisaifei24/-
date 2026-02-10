import sys
import random
import threading
import time
import keyboard
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLabel, QPushButton, QComboBox,
    QSpinBox, QVBoxLayout, QHBoxLayout, QGroupBox, QMessageBox, QFrame
)
from PyQt5.QtCore import Qt, QRect, pyqtSignal, QThread, QTimer
from PyQt5.QtGui import QCursor, QPainter, QColor, QPen, QFont
import pyautogui

pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.01

class RegionSelector(QWidget):
    region_selected = pyqtSignal(tuple)

    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setMouseTracking(True)
        
        screen = QApplication.primaryScreen().geometry()
        self.setGeometry(screen)
        self.start_pos = None
        self.end_pos = None
        self.is_selecting = False
        self.showFullScreen()
        self.setCursor(Qt.CrossCursor)
        
        self.activateWindow()
        QApplication.setActiveWindow(self)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 120))
        
        if self.start_pos and self.end_pos:
            rect = QRect(self.start_pos, self.end_pos)
            painter.setPen(QPen(QColor(0, 255, 100), 2, Qt.DashLine))
            painter.setBrush(QColor(0, 255, 100, 40))
            painter.drawRect(rect)
            
            w, h = abs(rect.width()), abs(rect.height())
            info_text = f"区域尺寸: {w}×{h} 像素\n松开鼠标确认 | ESC 取消"
            painter.setPen(QColor(255, 255, 255))
            painter.setFont(QFont("Arial", 12, QFont.Bold))
            painter.drawText(rect.adjusted(10, 10, -10, -10), Qt.AlignTop | Qt.AlignLeft, info_text)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.start_pos = event.pos()
            self.end_pos = event.pos()
            self.is_selecting = True
            self.update()

    def mouseMoveEvent(self, event):
        if self.is_selecting:
            self.end_pos = event.pos()
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self.is_selecting:
            self.is_selecting = False
            x1, y1 = self.start_pos.x(), self.start_pos.y()
            x2, y2 = self.end_pos.x(), self.end_pos.y()
            region = (min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2))
            if abs(x2-x1) >= 5 and abs(y2-y1) >= 5:
                self.region_selected.emit(region)
            self.close()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.close()

class ClickWorker(QThread):
    status_update = pyqtSignal(str)
    finished_signal = pyqtSignal()

    def __init__(self, region, frequency, button):
        super().__init__()
        self.region = region
        self.frequency = frequency
        self.button = button
        self._stop_flag = False

    def stop(self):
        self._stop_flag = True

    def run(self):
        self.status_update.emit("▶ 运行中（按 ESC 或移至左上角紧急停止）")
        
        def esc_listener():
            keyboard.wait('esc')
            if not self._stop_flag:
                self._stop_flag = True
        threading.Thread(target=esc_listener, daemon=True).start()
        
        interval = 1.0 / self.frequency
        x1, y1, x2, y2 = self.region
        
        try:
            while not self._stop_flag:
                if x2 - x1 > 5 and y2 - y1 > 5:
                    x = random.randint(x1, x2)
                    y = random.randint(y1, y2)
                    pyautogui.moveTo(x, y, duration=0.05, tween=pyautogui.linear)
                pyautogui.click(button=self.button)
                
                start = time.perf_counter()
                while (time.perf_counter() - start) < interval and not self._stop_flag:
                    time.sleep(0.005)
        except pyautogui.FailSafeException:
            self.status_update.emit("⚠ 紧急停止触发（鼠标移至左上角）")
        except Exception as e:
            self.status_update.emit(f"❌ 运行错误: {str(e)[:50]}")
        finally:
            self.finished_signal.emit()
            self.status_update.emit("⏹ 已安全停止")

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("🖱️ 智能鼠标连点器 v2.2")
        self.setGeometry(300, 200, 420, 400)
        self.selected_region = None
        self.click_thread = None
        self.selector = None
        
        # 全局样式（精简，键位按钮样式单独设置）
        self.setStyleSheet("""
            QMainWindow { background-color: #f8f9fa; }
            QGroupBox { 
                font-weight: bold; 
                border: 1.5px solid #4a90e2; 
                border-radius: 6px; 
                margin-top: 10px; 
                padding-top: 15px;
            }
            QGroupBox::title { 
                subcontrol-origin: margin; 
                left: 10px; 
                padding: 0 5px; 
                color: #2c3e50;
            }
            QLabel { color: #2c3e50; }
            QStatusBar { background-color: #ecf0f1; color: #2c3e50; }
            QComboBox, QSpinBox {
                padding: 4px;
                border: 1px solid #ddd;
                border-radius: 3px;
                background: white;
            }
        """)
        
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setSpacing(18)
        layout.setContentsMargins(25, 25, 25, 25)

        # 频率设置
        freq_group = QGroupBox("⏱️ 点击频率")
        freq_layout = QHBoxLayout()
        self.freq_preset = QComboBox()
        self.freq_preset.addItems(["低速 (5Hz)", "中速 (10Hz)", "高速 (20Hz)", "极速 (50Hz)", "自定义"])
        self.freq_preset.setStyleSheet("padding: 3px;")
        self.freq_preset.currentTextChanged.connect(self.on_freq_change)
        self.custom_freq = QSpinBox()
        self.custom_freq.setRange(1, 200)
        self.custom_freq.setValue(10)
        self.custom_freq.setSuffix(" Hz")
        self.custom_freq.setEnabled(False)
        self.custom_freq.setStyleSheet("padding: 3px;")
        freq_layout.addWidget(QLabel("模式:"))
        freq_layout.addWidget(self.freq_preset)
        freq_layout.addWidget(QLabel("自定义:"))
        freq_layout.addWidget(self.custom_freq)
        freq_layout.addStretch()
        freq_group.setLayout(freq_layout)
        layout.addWidget(freq_group)

        # 鼠标键位（重点优化区域）
        btn_group = QGroupBox("🖱️ 鼠标键位（点击切换）")
        btn_layout = QHBoxLayout()
        self.btn_left = QPushButton("左键")
        self.btn_right = QPushButton("右键")
        self.btn_middle = QPushButton("中键")
        
        # =============== 关键优化：键位按钮专属样式 ===============
        # 未选中基础样式
        base_style = """
            QPushButton {
                background-color: #4a90e2; 
                color: white; 
                border: none; 
                border-radius: 5px; 
                padding: 10px 15px;
                font-weight: bold;
                font-size: 13px;
                min-width: 85px;
            }
            QPushButton:hover {
                background-color: #3a7bc8;
            }
            QPushButton:pressed {
                background-color: #2a6299;
            }
        """
        # 选中状态增强样式（颜色加深 + 金色边框高亮）
        checked_style = """
            QPushButton:checked {
                background-color: #1a5276;  /* 深蓝色 */
                border: 2px solid #f39c12;  /* 金色边框 */
                padding: 8px 13px;          /* 补偿边框占用 */
            }
            QPushButton:checked:hover {
                background-color: #154360;
            }
        """
        
        # 应用组合样式
        btn_style = base_style + checked_style
        for btn in [self.btn_left, self.btn_right, self.btn_middle]:
            btn.setCheckable(True)
            btn.setStyleSheet(btn_style)
            btn_layout.addWidget(btn)
        self.btn_left.setChecked(True)  # 默认选中左键（自动触发:checked样式）
        # ========================================================
        
        btn_group.setLayout(btn_layout)
        layout.addWidget(btn_group)

        # 区域选择
        area_group = QGroupBox("📦 点击区域")
        area_layout = QVBoxLayout()
        self.area_label = QLabel("未选择区域\n（点击下方按钮进入全屏框选）")
        self.area_label.setFrameStyle(QFrame.Box | QFrame.Sunken)
        self.area_label.setAlignment(Qt.AlignCenter)
        self.area_label.setMinimumHeight(60)
        self.area_label.setStyleSheet("background-color: #ffffff; border: 1px dashed #95a5a6; color: #7f8c8d;")
        self.area_label.setWordWrap(True)
        select_btn = QPushButton("🖥️ 全屏框选点击区域")
        select_btn.setStyleSheet("""
            QPushButton {
                background-color: #27ae60; 
                color: white; 
                border: none; 
                border-radius: 5px; 
                padding: 10px; 
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #219653;
            }
        """)
        select_btn.clicked.connect(self.start_region_selection)
        area_layout.addWidget(self.area_label)
        area_layout.addWidget(select_btn)
        area_group.setLayout(area_layout)
        layout.addWidget(area_group)

        # 控制按钮
        ctrl_layout = QHBoxLayout()
        self.start_btn = QPushButton("▶ 启动连点")
        self.stop_btn = QPushButton("⏹ 停止")
        self.stop_btn.setEnabled(False)
        self.start_btn.setFixedHeight(48)
        self.stop_btn.setFixedHeight(48)
        self.start_btn.setStyleSheet("""
            QPushButton {
                background-color: #27ae60; 
                color: white; 
                border: none; 
                border-radius: 5px; 
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #219653;
            }
            QPushButton:pressed {
                background-color: #1e8449;
            }
        """)
        self.stop_btn.setStyleSheet("""
            QPushButton {
                background-color: #e74c3c; 
                color: white; 
                border: none; 
                border-radius: 5px; 
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #c0392b;
            }
            QPushButton:pressed {
                background-color: #a93226;
            }
            QPushButton:disabled {
                background-color: #bdc3c7;
                color: #95a5a6;
            }
        """)
        self.start_btn.clicked.connect(self.start_clicking)
        self.stop_btn.clicked.connect(self.stop_clicking)
        ctrl_layout.addWidget(self.start_btn)
        ctrl_layout.addWidget(self.stop_btn)
        layout.addLayout(ctrl_layout)

        # 状态栏
        self.status_label = QLabel("💡 就绪 | 提示：框选区域后启动，ESC 可紧急停止")
        self.status_label.setStyleSheet("color: #2c3e50; padding: 4px; font-size: 13px;")
        status_bar = self.statusBar()
        status_bar.addWidget(self.status_label)
        status_bar.setStyleSheet("background-color: #ecf0f1;")

        # 信号连接（样式已通过:checked自动处理，无需额外逻辑）
        self.btn_left.clicked.connect(lambda: self.uncheck_others(self.btn_left))
        self.btn_right.clicked.connect(lambda: self.uncheck_others(self.btn_right))
        self.btn_middle.clicked.connect(lambda: self.uncheck_others(self.btn_middle))

    def uncheck_others(self, checked_btn):
        """互斥选择：仅保留当前按钮选中状态"""
        for btn in [self.btn_left, self.btn_right, self.btn_middle]:
            if btn != checked_btn:
                btn.setChecked(False)
        # 选中按钮自动应用 :checked 样式（深蓝+金边框）

    def on_freq_change(self, text):
        self.custom_freq.setEnabled("自定义" in text)

    def restore_main_window(self):
        """确保主窗口显示在最前并获得焦点"""
        self.showNormal()
        self.raise_()
        self.activateWindow()
        QApplication.processEvents()
        QTimer.singleShot(100, lambda: self.status_label.setText(
            "✅ 区域已设置 | 请选择键位并启动" if self.selected_region else "💡 就绪 | 请框选点击区域"
        ))

    def start_region_selection(self):
        if self.selector and self.selector.isVisible():
            self.selector.close()
        
        info = QMessageBox(self)
        info.setWindowTitle("区域选择说明")
        info.setText("📌 框选操作指南：\n"
                    "1️⃣ 全屏半透明窗口将覆盖屏幕\n"
                    "2️⃣ 按住鼠标左键拖拽选择区域\n"
                    "3️⃣ 松开鼠标确认选择（需≥5×5像素）\n"
                    "4️⃣ 按 ESC 键可随时取消")
        info.setIcon(QMessageBox.Information)
        info.setStandardButtons(QMessageBox.Ok)
        info.exec_()
        
        self.selector = RegionSelector()
        self.selector.region_selected.connect(self.update_region)
        self.selector.destroyed.connect(self.restore_main_window)
        self.selector.show()

    def update_region(self, region):
        self.selected_region = region
        x1, y1, x2, y2 = region
        self.area_label.setText(
            f"✓ 区域已设置:\n({x1}, {y1}) → ({x2}, {y2})\n"
            f"尺寸: {x2-x1}×{y2-y1} 像素"
        )
        self.area_label.setStyleSheet("""
            background-color: #e8f5e9; 
            border: 2px solid #2ecc71; 
            color: #27ae60; 
            font-weight: bold;
            border-radius: 4px;
        """)
        self.status_label.setText(f"✅ 区域设置成功 | 宽:{x2-x1}px 高:{y2-y1}px | 请确认键位后启动")

    def get_selected_button(self):
        if self.btn_left.isChecked(): return 'left'
        if self.btn_right.isChecked(): return 'right'
        if self.btn_middle.isChecked(): return 'middle'
        return 'left'

    def get_frequency(self):
        if "自定义" in self.freq_preset.currentText():
            return self.custom_freq.value()
        maps = {"低速 (5Hz)": 5, "中速 (10Hz)": 10, "高速 (20Hz)": 20, "极速 (50Hz)": 50}
        return maps.get(self.freq_preset.currentText(), 10)

    def start_clicking(self):
        if not self.selected_region:
            QMessageBox.warning(self, "⚠️ 区域未设置", "请先点击「全屏框选点击区域」设置有效区域！")
            return
        
        if self.click_thread and self.click_thread.isRunning():
            return
        
        freq = self.get_frequency()
        button = self.get_selected_button()
        x1, y1, x2, y2 = self.selected_region
        
        if x2 - x1 < 5 or y2 - y1 < 5:
            QMessageBox.warning(self, "⚠️ 区域无效", "区域尺寸过小！请重新框选至少 5×5 像素的区域")
            return
        
        if freq > 50:
            reply = QMessageBox.question(
                self, "⚠️ 高频操作确认",
                f"设置频率 {freq}Hz 可能导致:\n• 系统卡顿\n• 游戏反作弊检测\n• 鼠标失控风险\n\n确认继续？",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if reply == QMessageBox.No:
                return
        
        self.click_thread = ClickWorker(self.selected_region, freq, button)
        self.click_thread.status_update.connect(self.update_status)
        self.click_thread.finished_signal.connect(self.on_click_finished)
        self.click_thread.start()
        
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        mode = "随机区域点击" if (x2-x1>10 and y2-y1>10) else "固定点点击"
        self.update_status(f"▶ 运行中 | {mode} | {freq}Hz | {button}键 | ESC紧急停止")

    def stop_clicking(self):
        if self.click_thread and self.click_thread.isRunning():
            self.click_thread.stop()
            self.update_status("⏹ 正在停止...")

    def on_click_finished(self):
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)

    def update_status(self, text):
        self.status_label.setText(text)
        if "已安全停止" in text or "⚠" in text or "❌" in text:
            self.start_btn.setEnabled(True)
            self.stop_btn.setEnabled(False)
            if "⚠" in text or "❌" in text:
                self.status_label.setStyleSheet("color: #e74c3c; font-weight: bold; padding: 4px;")
            else:
                self.status_label.setStyleSheet("color: #2c3e50; padding: 4px; font-size: 13px;")

    def closeEvent(self, event):
        if self.click_thread and self.click_thread.isRunning():
            self.click_thread.stop()
            self.click_thread.wait(1500)
        if self.selector and self.selector.isVisible():
            self.selector.close()
        event.accept()

if __name__ == "__main__":
    if hasattr(Qt, 'AA_EnableHighDpiScaling'):
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    if hasattr(Qt, 'AA_UseHighDpiPixmaps'):
        QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    
    app = QApplication(sys.argv)
    app.setApplicationName("MouseClickerPro")
    
    font = QFont("Microsoft YaHei UI", 10) if sys.platform == "win32" else QFont("Arial", 10)
    app.setFont(font)
    
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())