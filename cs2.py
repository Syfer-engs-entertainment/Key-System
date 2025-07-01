import sys
import time
import threading
import json
import os
import math
import struct
import requests
import pymem
import pymem.process
import win32api
import win32con
import win32gui
import psutil
import webbrowser
from PyQt6.QtWidgets import QMessageBox
from PyQt6 import QtWidgets, QtCore, QtGui
from PyQt6.QtWidgets import QApplication

def get_offsets_and_client_dll():
    try:
        offsets_url = "https://raw.githubusercontent.com/Skeleton-Archive/cs2-offsets/refs/heads/main/offsets.json"
        client_dll_url = "https://raw.githubusercontent.com/Skeleton-Archive/cs2-offsets/refs/heads/main/client_dll.json"

        offsets_response = requests.get(offsets_url, timeout=10)
        client_dll_response = requests.get(client_dll_url, timeout=10)

        return offsets_response.json(), client_dll_response.json()
    except:
        return {}, {}

def w2s_batch(view_matrix, positions, width, height):
    results = []
    for x, y, z in positions:
        w = view_matrix[12] * x + view_matrix[13] * y + view_matrix[14] * z + view_matrix[15]
        if w < 0.01:
            results.append((-999, -999))
            continue

        screen_x = (view_matrix[0] * x + view_matrix[1] * y + view_matrix[2] * z + view_matrix[3]) / w
        screen_y = (view_matrix[4] * x + view_matrix[5] * y + view_matrix[6] * z + view_matrix[7]) / w

        x = (width / 2.0) + (0.5 * screen_x * width + 0.5)
        y = (height / 2.0) - (0.5 * screen_y * height + 0.5)

        results.append((int(x), int(y)))
    return results

def load_settings():
    try:
        with open("cheat_settings.json", "r") as f:
            return json.load(f)
    except:
        return {
            "aim_active": False,
            "aim_key": "CTRL",
            "aim_radius": 80,
            "aim_smooth": 3.0,
            "aim_target": "Head",  # Added for completeness
            "aim_prediction": False,  # New feature: prediction toggle
            "aim_fov_type": "Circle",  # New feature: "Circle" or "Rectangle" FOV shapes
            "aim_auto_shoot": False,  # New feature: Automatic shooting when aim locked
            "fov_show": True,
            "fov_color": (255, 255, 255, 100),
            "esp_active": True,
            "esp_color": (255, 255, 255, 255),
            "esp_box_color": (0, 255, 0, 255),
            "esp_health_color": (255, 0, 0, 255),
            "esp_show_box": True,
            "esp_show_health": False,
            "esp_show_name": False,
            "esp_show_weapon_name": False,
            "esp_show_distance": False,
            "esp_show_skeleton_bones": False,
            "esp_health_gradient": False,
            "esp_name_bold": False,
            "mesh_enabled": False,
            "mesh_wireframe": False,
            "mesh_thickness": 2,
            "mesh_color": (0, 255, 255, 128),
            "mesh_distance": 1500,
        }

def save_settings(settings):
    try:
        with open("cheat_settings.json", "w") as f:
            json.dump(settings, f, indent=2)
    except:
        pass

current_settings = load_settings()

def get_current_settings():
    return current_settings

class AnimatedSlider(QtWidgets.QSlider):
    def __init__(self, orientation):
        super().__init__(orientation)
        self.setStyleSheet("""
            QSlider::groove:horizontal {
                border: none;
                height: 8px;
                margin: 0 10px;
                border-radius: 4px;
                background: #222;
            }
            QSlider::sub-page:horizontal {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #8000ff, stop:1 #a64dff);
                border-radius: 4px;
            }
            QSlider::handle:horizontal {
                background: white;
                border: 1px solid #a64dff;
                width: 16px;
                margin: -6px 0;
                border-radius: 8px;
            }
            QSlider::handle:horizontal:hover {
                background: #eee;
                border: 1px solid #c58aff;
            }
        """)

class ColorPicker(QtWidgets.QPushButton):
    colorChanged = QtCore.pyqtSignal()

    def __init__(self, color):
        super().__init__()
        self.color = color
        self.setFixedSize(40, 30)
        self.update_style()
        self.clicked.connect(self.pick_color)

    def update_style(self):
        r, g, b = self.color[:3]
        alpha = self.color[3] if len(self.color) > 3 else 255
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: rgba({r}, {g}, {b}, {alpha});
                border: 2px solid #fff;
                border-radius: 6px;
            }}
            QPushButton:hover {{
                border: 2px solid #ccc;
            }}
        """)

    def pick_color(self):
        color = QtWidgets.QColorDialog.getColor(QtGui.QColor(*self.color[:3]))
        if color.isValid():
            alpha = self.color[3] if len(self.color) > 3 else 255
            self.color = (color.red(), color.green(), color.blue(), alpha)
            self.update_style()
            self.colorChanged.emit()

class ESPPreviewWidget(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.setMinimumSize(200, 300)
        self.settings = get_current_settings()
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Fixed, QtWidgets.QSizePolicy.Policy.Fixed)
        self.setStyleSheet("background-color: rgba(20, 20, 20, 220); border-radius: 8px;")
        self.font = QtGui.QFont("Arial", 12, QtGui.QFont.Weight.Bold)
        self.small_font = QtGui.QFont("Arial", 10, QtGui.QFont.Weight.Normal)
        self.box_alpha = 255

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)

        rect_w = 100
        rect_h = 200
        rect_x = (self.width() - rect_w) // 2
        rect_y = (self.height() - rect_h) // 2

        settings = get_current_settings()

        # Draw box ESP if enabled
        if settings.get("esp_show_box", False) and settings.get("esp_active", False):
            box_color = QtGui.QColor(*settings.get("esp_box_color", (0, 255, 0, 255)))
            box_color.setAlpha(self.box_alpha)
            pen = QtGui.QPen(box_color, 2)
            painter.setPen(pen)
            painter.setBrush(QtCore.Qt.BrushStyle.NoBrush)
            painter.drawRect(rect_x, rect_y, rect_w, rect_h)

        # Draw health bar if enabled and health shown
        if settings.get("esp_show_health", False) and settings.get("esp_active", False):
            health = 75  # example dummy value
            bar_height = int(rect_h * (health / 100))
            bar_width = 8
            bar_x = rect_x - bar_width - 5
            bar_y = rect_y + rect_h - bar_height
            if settings.get("esp_health_gradient", False):
                gradient = QtGui.QLinearGradient(bar_x, bar_y, bar_x, bar_y + bar_height)
                gradient.setColorAt(0, QtGui.QColor(0, 255, 0, 180))
                gradient.setColorAt(1, QtGui.QColor(255, 0, 0, 180))
                painter.setPen(QtCore.Qt.PenStyle.NoPen)
                painter.setBrush(gradient)
                painter.drawRect(bar_x, bar_y, bar_width, bar_height)
                painter.setBrush(QtGui.QColor(50, 50, 50, 150))
                painter.drawRect(bar_x, rect_y, bar_width, rect_h - bar_height)
            else:
                health_color = QtGui.QColor(*settings.get("esp_health_color", (255, 0, 0, 255)))
                painter.setPen(QtCore.Qt.PenStyle.NoPen)
                painter.setBrush(health_color)
                painter.drawRect(bar_x, bar_y, bar_width, bar_height)
                painter.setBrush(QtGui.QColor(50, 50, 50, 150))
                painter.drawRect(bar_x, rect_y, bar_width, rect_h - bar_height)

        # Draw name if enabled
        if settings.get("esp_show_name", False) and settings.get("esp_active", False):
            name = "Player123"
            name_color = QtGui.QColor(*settings.get("esp_name_color", (255, 255, 255, 255)))
            font_weight = QtGui.QFont.Weight.Bold if settings.get("esp_name_bold", False) else QtGui.QFont.Weight.Normal
            font = QtGui.QFont("Arial", 12, font_weight)
            painter.setFont(font)
            painter.setPen(name_color)
            text_width = painter.fontMetrics().horizontalAdvance(name)
            x = rect_x + rect_w // 2 - text_width // 2
            y = rect_y - 10
            painter.drawText(x, y, name)

        # Draw weapon name if enabled
        if settings.get("esp_show_weapon_name", False) and settings.get("esp_active", False):
            weapon = "AK-47"
            weapon_color = QtGui.QColor(*settings.get("esp_weapon_color", (255, 255, 0, 255)))
            painter.setFont(self.small_font)
            painter.setPen(weapon_color)
            text_width = painter.fontMetrics().horizontalAdvance(weapon)
            x = rect_x + rect_w // 2 - text_width // 2
            y = rect_y + rect_h + 20
            painter.drawText(x, y, weapon)

        # Draw distance if enabled
        if settings.get("esp_show_distance", False) and settings.get("esp_active", False):
            dist_text = "120m"
            dist_color = QtGui.QColor(200, 200, 255, 255)
            painter.setFont(QtGui.QFont("Arial", 9))
            painter.setPen(dist_color)
            text_width = painter.fontMetrics().horizontalAdvance(dist_text)
            x = rect_x + rect_w // 2 - text_width // 2
            y = rect_y - 25
            painter.drawText(x, y, dist_text)

        painter.end()

class SettingsMenu(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.settings = get_current_settings()
        self.old_pos = None
        self.init_ui()
        self.add_new_aimbot_controls()
        self.esp_preview_widget = ESPPreviewWidget()
        self.side_preview_layout.addWidget(self.esp_preview_widget)
        self.esp_preview_widget.setVisible(True)

    def init_ui(self):
        self.setWindowTitle("Syfer-eng")
        self.setFixedSize(900, 500)  # Increased width to accommodate preview
        self.setWindowFlags(QtCore.Qt.WindowType.FramelessWindowHint | QtCore.Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TranslucentBackground)

        main_layout = QtWidgets.QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        background = QtWidgets.QWidget()
        background.setStyleSheet("background-color: rgba(30, 30, 30, 180); border-radius: 10px;")
        blur = QtWidgets.QGraphicsBlurEffect()
        blur.setBlurRadius(0)
        background.setGraphicsEffect(blur)

        bg_layout = QtWidgets.QHBoxLayout(background)
        bg_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(background)

        # Sidebar and logo
        left_panel = QtWidgets.QVBoxLayout()

        img_label = QtWidgets.QLabel()
        logo_path = "logo.png"
        logo_url = "https://raw.githubusercontent.com/Skeleton-Archive/cs2-offsets/refs/heads/main/logo.png"

        # Download logo if missing or invalid
        if not os.path.isfile(logo_path):
            try:
                response = requests.get(logo_url, timeout=10)
                if response.status_code == 200:
                    with open(logo_path, "wb") as f:
                        f.write(response.content)
            except Exception as e:
                print(f"Failed to download logo: {e}")

        pixmap = QtGui.QPixmap(logo_path)
        if pixmap.isNull():
            pixmap = QtGui.QPixmap(64, 64)
            pixmap.fill(QtGui.QColor("transparent"))
        else:
            pixmap = pixmap.scaled(64, 64, QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                                   QtCore.Qt.TransformationMode.SmoothTransformation)
        img_label.setPixmap(pixmap)
        img_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop | QtCore.Qt.AlignmentFlag.AlignLeft)
        left_panel.addWidget(img_label)

        self.sidebar = QtWidgets.QListWidget()
        self.sidebar.setFixedWidth(150)
        self.sidebar.addItem("Combat")
        self.sidebar.addItem("Visuals")
        self.sidebar.addItem("Misc")
        self.sidebar.addItem("Mesh")
        self.sidebar.setStyleSheet("""
            QListWidget {
                background-color: transparent;
                color: #fff;
                font-weight: bold;
                border-right: 1px solid #333;
            }
            QListWidget::item:selected {
                background-color: #8000ff;
                color: white;
            }
        """)
        left_panel.addWidget(self.sidebar)

        self.pages = QtWidgets.QStackedWidget()
        self.pages.addWidget(self.combat_tab())
        self.pages.addWidget(self.visual_tab())
        self.pages.addWidget(self.misc_tab())
        self.pages.addWidget(self.mesh_tab())

        self.sidebar.currentRowChanged.connect(self.pages.setCurrentIndex)
        self.sidebar.setCurrentRow(0)

        bg_layout.addLayout(left_panel)
        bg_layout.addWidget(self.pages)

        # Add ESP preview area beside the pages
        self.side_preview_layout = QtWidgets.QVBoxLayout()
        self.side_preview_layout.setContentsMargins(10, 10, 10, 10)
        bg_layout.addLayout(self.side_preview_layout)

    def styled_checkbox(self, text, checked):
        container = QtWidgets.QWidget()
        layout = QtWidgets.QHBoxLayout(container)
        layout.setContentsMargins(4, 4, 4, 4)

        checkbox = QtWidgets.QCheckBox()
        checkbox.setChecked(checked)
        checkbox.setStyleSheet("""
            QCheckBox::indicator {
                width: 30px;
                height: 14px;
                border-radius: 7px;
                background-color: transparent;
                border: 2px solid #666;
            }
            QCheckBox::indicator:checked {
                background-color: #8000ff;
                border: 2px solid #8000ff;
            }
        """)

        label = QtWidgets.QLabel(text)
        label.setStyleSheet("color: white; font-weight: bold; margin-left: 8px;")

        layout.addWidget(checkbox)
        layout.addWidget(label)
        layout.addStretch()

        container.checkbox = checkbox
        return container

    def _combine_toggle_and_color(self, checkbox_wrapper, color_picker):
        layout = QtWidgets.QHBoxLayout()
        layout.addWidget(checkbox_wrapper)
        layout.addStretch()
        layout.addWidget(color_picker)
        wrapper = QtWidgets.QWidget()
        wrapper.setLayout(layout)
        return wrapper

    def combat_tab(self):
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)

        self.aim_active = self.styled_checkbox("Enable Aimbot", self.settings.get("aim_active", True))
        self.aim_active.checkbox.toggled.connect(self.update_settings)
        layout.addWidget(self.aim_active)

        layout.addWidget(QtWidgets.QLabel("Aim Key"))
        self.aim_key = QtWidgets.QComboBox()
        self.aim_key.addItems(["CTRL", "SHIFT", "ALT", "SPACE", "X", "C", "V", "F", "G", "H"])
        self.aim_key.setCurrentText(self.settings.get("aim_key", "CTRL"))
        self.aim_key.currentTextChanged.connect(self.update_settings)
        layout.addWidget(self.aim_key)

        layout.addWidget(QtWidgets.QLabel("FOV Radius"))
        self.aim_radius = AnimatedSlider(QtCore.Qt.Orientation.Horizontal)
        self.aim_radius.setRange(10, 200)
        self.aim_radius.setValue(self.settings.get("aim_radius", 80))
        self.aim_radius.valueChanged.connect(self.update_settings)
        layout.addWidget(self.aim_radius)

        layout.addWidget(QtWidgets.QLabel("Smoothing"))
        self.aim_smooth = AnimatedSlider(QtCore.Qt.Orientation.Horizontal)
        self.aim_smooth.setRange(7, 100)
        self.aim_smooth.setValue(int(self.settings.get("aim_smooth", 3.0) * 10))
        self.aim_smooth.valueChanged.connect(self.update_settings)
        layout.addWidget(self.aim_smooth)

        layout.addWidget(QtWidgets.QLabel("Aim Target"))
        self.aim_target = QtWidgets.QComboBox()
        self.aim_target.addItems(["Head", "Neck", "Chest", "Stomach"])
        self.aim_target.setCurrentText(self.settings.get("aim_target", "Head"))
        self.aim_target.currentTextChanged.connect(self.update_settings)
        layout.addWidget(self.aim_target)

        # Placeholder for new controls added separately

        layout.addStretch()
        return widget

    def add_new_aimbot_controls(self):
        layout = self.aim_active.parent().layout()

        self.aim_prediction_checkbox = self.styled_checkbox("Enable Prediction", self.settings.get("aim_prediction", False))
        self.aim_prediction_checkbox.checkbox.toggled.connect(self.update_settings)
        layout.addWidget(self.aim_prediction_checkbox)

        fov_type_label = QtWidgets.QLabel("FOV Type")
        fov_type_label.setStyleSheet("color: white; font-weight: bold; margin-top: 10px;")
        layout.addWidget(fov_type_label)
        self.aim_fov_type_combo = QtWidgets.QComboBox()
        self.aim_fov_type_combo.addItems(["Circle", "Rectangle"])
        self.aim_fov_type_combo.setCurrentText(self.settings.get("aim_fov_type", "Circle"))
        self.aim_fov_type_combo.currentTextChanged.connect(self.update_settings)
        layout.addWidget(self.aim_fov_type_combo)

        self.aim_auto_shoot_checkbox = self.styled_checkbox("Auto Shoot", self.settings.get("aim_auto_shoot", False))
        self.aim_auto_shoot_checkbox.checkbox.toggled.connect(self.update_settings)
        layout.addWidget(self.aim_auto_shoot_checkbox)

    def visual_tab(self):
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QFormLayout(widget)

        self.esp_active = self.styled_checkbox("Enable ESP", self.settings.get("esp_active", True))
        self.esp_active.checkbox.toggled.connect(self.update_settings)
        layout.addRow(self.esp_active)

        self.esp_show_box = self.styled_checkbox("Show Box", self.settings.get("esp_show_box", True))
        self.esp_show_box.checkbox.toggled.connect(self.update_settings)
        self.esp_box_color = ColorPicker(self.settings.get("esp_box_color", (0, 255, 0, 255)))
        self.esp_box_color.colorChanged.connect(self.update_settings)
        layout.addRow(self._combine_toggle_and_color(self.esp_show_box, self.esp_box_color))

        self.esp_show_health = self.styled_checkbox("Show Health", self.settings.get("esp_show_health", True))
        self.esp_show_health.checkbox.toggled.connect(self.update_settings)
        self.esp_health_color = ColorPicker(self.settings.get("esp_health_color", (255, 0, 0, 255)))
        self.esp_health_color.colorChanged.connect(self.update_settings)
        layout.addRow(self._combine_toggle_and_color(self.esp_show_health, self.esp_health_color))

        self.esp_health_gradient = self.styled_checkbox("Health Gradient", self.settings.get("esp_health_gradient", True))
        self.esp_health_gradient.checkbox.toggled.connect(self.update_settings)
        layout.addRow(self.esp_health_gradient)

        self.esp_show_name = self.styled_checkbox("Show Name", self.settings.get("esp_show_name", True))
        self.esp_show_name.checkbox.toggled.connect(self.update_settings)
        self.esp_name_color = ColorPicker(self.settings.get("esp_name_color", (255, 255, 255, 255)))
        self.esp_name_color.colorChanged.connect(self.update_settings)
        layout.addRow(self._combine_toggle_and_color(self.esp_show_name, self.esp_name_color))

        self.esp_name_bold = self.styled_checkbox("Bold Name Text", self.settings.get("esp_name_bold", True))
        self.esp_name_bold.checkbox.toggled.connect(self.update_settings)
        layout.addRow(self.esp_name_bold)

        self.esp_show_weapon = self.styled_checkbox("Show Weapon Name", self.settings.get("esp_show_weapon_name", True))
        self.esp_show_weapon.checkbox.toggled.connect(self.update_settings)
        self.esp_weapon_color = ColorPicker(self.settings.get("esp_weapon_color", (255, 255, 0, 255)))
        self.esp_weapon_color.colorChanged.connect(self.update_settings)
        layout.addRow(self._combine_toggle_and_color(self.esp_show_weapon, self.esp_weapon_color))

        self.esp_show_distance = self.styled_checkbox("Show Distance", self.settings.get("esp_show_distance", True))
        self.esp_show_distance.checkbox.toggled.connect(self.update_settings)
        layout.addRow(self.esp_show_distance)

        self.esp_show_bones = self.styled_checkbox("Bone ESP", self.settings.get("esp_show_skeleton_bones", True))
        self.esp_show_bones.checkbox.toggled.connect(self.update_settings)
        self.esp_color = ColorPicker(self.settings.get("esp_color", (255, 255, 255, 255)))
        self.esp_color.colorChanged.connect(self.update_settings)
        layout.addRow(self._combine_toggle_and_color(self.esp_show_bones, self.esp_color))

        # Fix addStretch on QFormLayout by adding a stretchy invisible spacer widget row
        spacer = QtWidgets.QWidget()
        spacer.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Expanding)
        layout.addRow(spacer)

        return widget

    def misc_tab(self):
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)

        self.pinwheel_toggle = self.styled_checkbox("Rainbow Pinwheel", self.settings.get("rainbow_pinwheel", False))
        self.pinwheel_toggle.checkbox.toggled.connect(self.update_settings)
        layout.addWidget(self.pinwheel_toggle)

        layout.addStretch()
        return widget

    def mesh_tab(self):
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QFormLayout(widget)

        self.mesh_enabled_checkbox = self.styled_checkbox("Enable Mesh ESP", self.settings.get("mesh_enabled", False))
        self.mesh_enabled_checkbox.checkbox.toggled.connect(self.update_settings)
        layout.addRow(self.mesh_enabled_checkbox)

        self.mesh_wireframe_checkbox = self.styled_checkbox("Wireframe Mode", self.settings.get("mesh_wireframe", True))
        self.mesh_wireframe_checkbox.checkbox.toggled.connect(self.update_settings)
        layout.addRow(self.mesh_wireframe_checkbox)

        self.mesh_thickness_slider = AnimatedSlider(QtCore.Qt.Orientation.Horizontal)
        self.mesh_thickness_slider.setRange(1, 10)
        self.mesh_thickness_slider.setValue(self.settings.get("mesh_thickness", 2))
        self.mesh_thickness_slider.valueChanged.connect(self.update_settings)
        thickness_label = QtWidgets.QLabel("Line Thickness")
        layout.addRow(thickness_label, self.mesh_thickness_slider)

        self.mesh_color_picker = ColorPicker(self.settings.get("mesh_color", (0, 255, 255, 128)))
        self.mesh_color_picker.colorChanged.connect(self.update_settings)
        layout.addRow(QtWidgets.QLabel("Mesh Color"), self.mesh_color_picker)

        self.mesh_distance_slider = AnimatedSlider(QtCore.Qt.Orientation.Horizontal)
        self.mesh_distance_slider.setRange(500, 5000)
        self.mesh_distance_slider.setValue(self.settings.get("mesh_distance", 1500))
        self.mesh_distance_slider.valueChanged.connect(self.update_settings)
        distance_label = QtWidgets.QLabel("Max Draw Distance")
        layout.addRow(distance_label, self.mesh_distance_slider)

        # Fix addStretch on QFormLayout by adding a stretchy invisible spacer widget row
        spacer = QtWidgets.QWidget()
        spacer.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Expanding)
        layout.addRow(spacer)

        return widget

    def update_settings(self):
        self.settings["aim_active"] = self.aim_active.checkbox.isChecked()
        self.settings["aim_key"] = self.aim_key.currentText()
        self.settings["aim_radius"] = self.aim_radius.value()
        self.settings["aim_smooth"] = self.aim_smooth.value() / 10.0
        self.settings["aim_target"] = self.aim_target.currentText()
        if hasattr(self, 'aim_prediction_checkbox'):
            self.settings["aim_prediction"] = self.aim_prediction_checkbox.checkbox.isChecked()
        if hasattr(self, 'aim_fov_type_combo'):
            self.settings["aim_fov_type"] = self.aim_fov_type_combo.currentText()
        if hasattr(self, 'aim_auto_shoot_checkbox'):
            self.settings["aim_auto_shoot"] = self.aim_auto_shoot_checkbox.checkbox.isChecked()

        self.settings["esp_active"] = self.esp_active.checkbox.isChecked()
        self.settings["esp_show_box"] = self.esp_show_box.checkbox.isChecked()
        self.settings["esp_show_health"] = self.esp_show_health.checkbox.isChecked()
        self.settings["esp_show_skeleton_bones"] = self.esp_show_bones.checkbox.isChecked()
        self.settings["esp_color"] = self.esp_color.color
        self.settings["esp_box_color"] = self.esp_box_color.color
        self.settings["esp_health_color"] = self.esp_health_color.color

        self.settings["esp_show_name"] = self.esp_show_name.checkbox.isChecked()
        self.settings["esp_name_color"] = self.esp_name_color.color
        self.settings["esp_name_bold"] = self.esp_name_bold.checkbox.isChecked()

        self.settings["esp_show_weapon_name"] = self.esp_show_weapon.checkbox.isChecked()
        self.settings["esp_weapon_color"] = self.esp_weapon_color.color

        self.settings["esp_show_distance"] = self.esp_show_distance.checkbox.isChecked()
        self.settings["esp_health_gradient"] = self.esp_health_gradient.checkbox.isChecked()

        self.settings["rainbow_pinwheel"] = self.pinwheel_toggle.checkbox.isChecked()

        if hasattr(self, "mesh_enabled_checkbox"):
            self.settings["mesh_enabled"] = self.mesh_enabled_checkbox.checkbox.isChecked()
        if hasattr(self, "mesh_wireframe_checkbox"):
            self.settings["mesh_wireframe"] = self.mesh_wireframe_checkbox.checkbox.isChecked()
        if hasattr(self, "mesh_thickness_slider"):
            self.settings["mesh_thickness"] = self.mesh_thickness_slider.value()
        if hasattr(self, "mesh_color_picker"):
            self.settings["mesh_color"] = self.mesh_color_picker.color
        if hasattr(self, "mesh_distance_slider"):
            self.settings["mesh_distance"] = self.mesh_distance_slider.value()

        save_settings(self.settings)
        # Update preview widget to repaint on settings change
        if hasattr(self, 'esp_preview_widget'):
            self.esp_preview_widget.update()

    def mousePressEvent(self, event):
        self.old_pos = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event):
        if self.old_pos:
            delta = event.globalPosition().toPoint() - self.old_pos
            self.move(self.pos() + delta)
            self.old_pos = event.globalPosition().toPoint()

def get_target_bone_index():
    settings = get_current_settings()
    bone_map = {
        "Head": 6,
        "Neck": 5,
        "Chest": 4,
        "Stomach": 2
    }
    return bone_map.get(settings.get("aim_target", "Head"), 6)

def aimbot_thread(pm, client, offsets, client_dll):
    key_map = {
        "CTRL": win32con.VK_CONTROL,
        "SHIFT": win32con.VK_SHIFT,
        "ALT": win32con.VK_MENU,
        "SPACE": win32con.VK_SPACE,
        "X": ord('X'),
        "C": ord('C'),
        "V": ord('V'),
        "F": ord('F'),
        "G": ord('G'),
        "H": ord('H')
    }

    dwEntityList = offsets.get('client.dll', {}).get('dwEntityList', 0)
    dwLocalPlayerPawn = offsets.get('client.dll', {}).get('dwLocalPlayerPawn', 0)
    dwViewMatrix = offsets.get('client.dll', {}).get('dwViewMatrix', 0)
    client_classes = client_dll.get('client.dll', {}).get('classes', {})
    c_base_entity = client_classes.get('C_BaseEntity', {}).get('fields', {})
    cskeleton_instance = client_classes.get('CSkeletonInstance', {}).get('fields', {})
    cc_playercontroller = client_classes.get('CCSPlayerController', {}).get('fields', {})

    m_iTeamNum = c_base_entity.get('m_iTeamNum', 0)
    m_lifeState = c_base_entity.get('m_lifeState', 0)
    m_pGameSceneNode = c_base_entity.get('m_pGameSceneNode', 0)
    m_modelState = cskeleton_instance.get('m_modelState', 0)
    m_hPlayerPawn = cc_playercontroller.get('m_hPlayerPawn', 0)

    dwClientState = offsets.get('engine.dll', {}).get('dwClientState', 0)
    dwClientState_ViewAngles = offsets.get('engine.dll', {}).get('dwClientState_ViewAngles', 0)

    def predict_position(x, y, z, vx, vy, vz, latency=0.05):
        return (x + vx * latency, y + vy * latency, z + vz * latency)

    while True:
        settings = get_current_settings()
        if not settings["aim_active"]:
            time.sleep(0.1)
            continue

        aim_key = key_map.get(settings["aim_key"], win32con.VK_CONTROL)
        if not win32api.GetAsyncKeyState(aim_key):
            time.sleep(0.005)
            continue

        try:
            view_matrix = [pm.read_float(client + dwViewMatrix + i * 4) for i in range(16)]
            local = pm.read_longlong(client + dwLocalPlayerPawn)
            if not local:
                time.sleep(0.005)
                continue
            local_team = pm.read_int(local + m_iTeamNum)
            entity_list = pm.read_longlong(client + dwEntityList)
            base = pm.read_longlong(entity_list + 0x10)

            width, height = win32api.GetSystemMetrics(0), win32api.GetSystemMetrics(1)
            crosshair_x, crosshair_y = width // 2, height // 2

            if dwClientState and dwClientState_ViewAngles:
                client_state = pm.read_int(dwClientState)
                if client_state:
                    pitch = pm.read_float(client_state + dwClientState_ViewAngles)
                    yaw = pm.read_float(client_state + dwClientState_ViewAngles + 0x4)

                    pitch_rad = math.radians(pitch)
                    yaw_rad = math.radians(yaw)
                    forward = (
                        math.cos(pitch_rad) * math.cos(yaw_rad),
                        math.cos(pitch_rad) * math.sin(yaw_rad),
                        math.sin(pitch_rad)
                    )
                    world_pos = (forward[0] * 1000, forward[1] * 1000, forward[2] * 1000)
                    proj_x, proj_y = w2s_batch(view_matrix, [world_pos], width, height)[0]
                    if 0 <= proj_x <= width and 0 <= proj_y <= height:
                        crosshair_x, crosshair_y = proj_x, proj_y

            fov_radius = settings["aim_radius"] / 100 * min(width, height) / 2

            closest_dist = float('inf')
            best_target = None

            target_bone = get_target_bone_index()

            for i in range(1, 64):
                try:
                    ctrl = pm.read_longlong(base + 0x78 * (i & 0x1FF))
                    if not ctrl:
                        continue
                    pawn = pm.read_longlong(ctrl + m_hPlayerPawn)
                    if not pawn:
                        continue
                    entry = pm.read_longlong(entity_list + 0x8 * ((pawn & 0x7FFF) >> 9) + 0x10)
                    if not entry:
                        continue
                    ent = pm.read_longlong(entry + 0x78 * (pawn & 0x1FF))
                    if not ent or ent == local:
                        continue
                    if pm.read_int(ent + m_iTeamNum) == local_team:
                        continue
                    if pm.read_int(ent + m_lifeState) != 256:
                        continue

                    scene = pm.read_longlong(ent + m_pGameSceneNode)
                    if not scene:
                        continue
                    bone_matrix = pm.read_longlong(scene + m_modelState + 0x80)
                    if not bone_matrix:
                        continue

                    x = pm.read_float(bone_matrix + target_bone * 0x20)
                    y = pm.read_float(bone_matrix + target_bone * 0x20 + 4)
                    z = pm.read_float(bone_matrix + target_bone * 0x20 + 8)

                    if settings.get("aim_prediction", False):
                        velocity_offset = 0x140  # example offset, adjust as necessary
                        try:
                            vx = pm.read_float(ent + velocity_offset)
                            vy = pm.read_float(ent + velocity_offset + 4)
                            vz = pm.read_float(ent + velocity_offset + 8)
                            x, y, z = predict_position(x, y, z, vx, vy, vz)
                        except:
                            pass

                    sx, sy = w2s_batch(view_matrix, [(x, y, z)], width, height)[0]
                    if sx <= 0 or sy <= 0:
                        continue

                    dx = sx - crosshair_x
                    dy = sy - crosshair_y

                    fov_type = settings.get("aim_fov_type", "Circle").lower()
                    if fov_type == "circle":
                        dist = math.hypot(dx, dy)
                        in_fov = dist < fov_radius
                    elif fov_type == "rectangle":
                        in_fov = abs(dx) < fov_radius and abs(dy) < fov_radius
                        dist = abs(dx) + abs(dy)
                    else:
                        dist = math.hypot(dx, dy)
                        in_fov = dist < fov_radius

                    if in_fov and dist < closest_dist:
                        closest_dist = dist
                        best_target = (sx, sy)

                except:
                    continue

            if best_target is not None:
                dx = best_target[0] - crosshair_x
                dy = best_target[1] - crosshair_y
                smooth = settings["aim_smooth"]
                move_x = int(dx / smooth)
                move_y = int(dy / smooth)

                if abs(move_x) < 1 and dx != 0:
                    move_x = 1 if dx > 0 else -1
                if abs(move_y) < 1 and dy != 0:
                    move_y = 1 if dy > 0 else -1

                win32api.mouse_event(win32con.MOUSEEVENTF_MOVE, move_x, move_y, 0, 0)

                if settings.get("aim_auto_shoot", False):
                    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
                    time.sleep(0.01)
                    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)

        except Exception:
            pass

        time.sleep(0.001)

class FastBoneESPWindow(QtWidgets.QWidget):
    def __init__(self, pm, offsets, client_dll):
        super().__init__()
        self.pm = pm
        self.offsets = offsets
        self.client_dll = client_dll
        self.client = pymem.process.module_from_name(self.pm.process_handle, "client.dll").lpBaseOfDll
        self.window_width, self.window_height = win32api.GetSystemMetrics(0), win32api.GetSystemMetrics(1)

        self.setGeometry(0, 0, self.window_width, self.window_height)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowFlags(
            QtCore.Qt.WindowType.FramelessWindowHint
            | QtCore.Qt.WindowType.WindowStaysOnTopHint
            | QtCore.Qt.WindowType.Tool
        )

        hwnd = self.winId()
        win32gui.SetWindowLong(
            hwnd,
            win32con.GWL_EXSTYLE,
            win32con.WS_EX_LAYERED | win32con.WS_EX_TRANSPARENT | win32con.WS_EX_TOOLWINDOW,
        )

        self.cache_offsets()

        self.bone_path = QtGui.QPainterPath()

        self.esp_pen = None
        self.box_pen = None

        self.font = QtGui.QFont("Arial", 12, QtGui.QFont.Weight.Bold)
        self.small_font = QtGui.QFont("Arial", 10, QtGui.QFont.Weight.Bold)

        self.fps_counter = 0
        self.last_fps_time = time.time()
        self.esp_fps = 0
        self.game_fps = 0

        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self.update_esp)
        self.timer.start(0)

    def cache_offsets(self):
        o = self.offsets.get("client.dll", {})
        c = self.client_dll.get("client.dll", {}).get("classes", {})

        self.dwEntityList = o.get("dwEntityList", 0)
        self.dwLocalPlayerPawn = o.get("dwLocalPlayerPawn", 0)
        self.dwViewMatrix = o.get("dwViewMatrix", 0)

        self.m_iTeamNum = c.get("C_BaseEntity", {}).get("fields", {}).get("m_iTeamNum", 0)
        self.m_lifeState = c.get("C_BaseEntity", {}).get("fields", {}).get("m_lifeState", 0)
        self.m_pGameSceneNode = c.get("C_BaseEntity", {}).get("fields", {}).get("m_pGameSceneNode", 0)
        self.m_modelState = c.get("CSkeletonInstance", {}).get("fields", {}).get("m_modelState", 0)
        self.m_hPlayerPawn = c.get("CCSPlayerController", {}).get("fields", {}).get("m_hPlayerPawn", 0)

        self.m_iHealth = c.get("C_BaseEntity", {}).get("fields", {}).get("m_iHealth", 0x100)
        self.m_szPlayerName = c.get("C_BaseEntity", {}).get("fields", {}).get("m_szPlayerName", 0x600)
        self.m_currentWeapon = c.get("C_BaseEntity", {}).get("fields", {}).get("m_currentWeapon", 0x700)

        self.bone_connections = [
            (6, 5), (5, 4), (4, 2), (2, 0),
            (4, 8), (8, 9), (9, 10),
            (4, 13), (13, 14), (14, 15),
            (0, 22), (22, 23), (23, 24),
            (0, 25), (25, 26), (26, 27),
        ]

        self.dwGameFPS = o.get("dwGameFPS", None)
        self.dwClientState = self.offsets.get("engine.dll", {}).get("dwClientState", 0)
        self.dwClientState_ViewAngles = self.offsets.get("engine.dll", {}).get("dwClientState_ViewAngles", 0)

    def read_string(self, address, max_length=32):
        try:
            data = self.pm.read_bytes(address, max_length)
            s = data.split(b'\x00', 1)[0]
            return s.decode(errors="ignore")
        except:
            return ""

    def update_esp(self):
        settings = get_current_settings()
        self.bone_path = QtGui.QPainterPath()

        self.fps_counter += 1
        current_time = time.time()
        if current_time - self.last_fps_time >= 1.0:
            self.esp_fps = self.fps_counter
            self.fps_counter = 0
            self.last_fps_time = current_time

        if self.dwGameFPS:
            try:
                fps_bytes = self.pm.read_bytes(self.client + self.dwGameFPS, 4)
                self.game_fps = struct.unpack("f", fps_bytes)[0]
                self.game_fps = max(0, min(self.game_fps, 1000))
            except:
                self.game_fps = 0
        else:
            self.game_fps = 0

        if not settings["esp_active"]:
            self.update()
            return

        players_to_draw = []

        try:
            view_matrix_bytes = self.pm.read_bytes(self.client + self.dwViewMatrix, 64)
            view_matrix = list(struct.unpack("16f", view_matrix_bytes))

            local = self.pm.read_longlong(self.client + self.dwLocalPlayerPawn)
            if not local:
                self.update()
                return

            local_team = self.pm.read_int(local + self.m_iTeamNum)
            entity_list = self.pm.read_longlong(self.client + self.dwEntityList)
            base = self.pm.read_longlong(entity_list + 0x10)

            local_pos = None
            try:
                local_scene = self.pm.read_longlong(local + self.m_pGameSceneNode)
                local_bone_matrix = self.pm.read_longlong(local_scene + self.m_modelState + 0x80) if local_scene else 0
                if local_bone_matrix:
                    local_x = self.pm.read_float(local_bone_matrix + 0 * 0x20)
                    local_y = self.pm.read_float(local_bone_matrix + 0 * 0x20 + 4)
                    local_z = self.pm.read_float(local_bone_matrix + 0 * 0x20 + 8)
                    local_pos = (local_x, local_y, local_z)
            except:
                local_pos = None

            for i in range(1, 64):
                try:
                    ctrl = self.pm.read_longlong(base + 0x78 * (i & 0x1FF))
                    if not ctrl:
                        continue

                    pawn = self.pm.read_longlong(ctrl + self.m_hPlayerPawn)
                    if not pawn:
                        continue

                    entry = self.pm.read_longlong(entity_list + 0x8 * ((pawn & 0x7FFF) >> 9) + 0x10)
                    if not entry:
                        continue

                    ent = self.pm.read_longlong(entry + 0x78 * (pawn & 0x1FF))
                    if not ent:
                        continue

                    # Skip local player
                    if ent == local:
                        continue

                    life_state = self.pm.read_int(ent + self.m_lifeState)
                    if life_state != 256:
                        continue

                    team_num = self.pm.read_int(ent + self.m_iTeamNum)
                    if team_num == local_team:
                        continue

                    scene = self.pm.read_longlong(ent + self.m_pGameSceneNode)
                    if not scene:
                        continue

                    bone_matrix = self.pm.read_longlong(scene + self.m_modelState + 0x80)
                    if not bone_matrix:
                        continue

                    health = 0
                    if self.m_iHealth != 0:
                        try:
                            health = self.pm.read_int(ent + self.m_iHealth)
                            if health < 0:
                                health = 0
                            elif health > 100:
                                health = 100
                        except:
                            health = 0

                    player_name = ""
                    if self.m_szPlayerName != 0:
                        try:
                            player_name = self.read_string(ent + self.m_szPlayerName, 32)
                        except:
                            player_name = ""

                    if not player_name or player_name.strip() == "":
                        player_name = "Bot"

                    weapon_name = ""
                    if self.m_currentWeapon != 0:
                        try:
                            weapon_ptr = self.pm.read_longlong(ent + self.m_currentWeapon)
                            if weapon_ptr:
                                weapon_name = self.read_string(weapon_ptr + 0x30, 32)
                        except:
                            weapon_name = ""

                    bone_positions = []
                    read_bytes = self.pm.read_bytes(bone_matrix, 28 * 0x20)
                    for bone_id in range(28):
                        offset = bone_id * 0x20
                        try:
                            x = struct.unpack_from("f", read_bytes, offset)[0]
                            y = struct.unpack_from("f", read_bytes, offset + 4)[0]
                            z = struct.unpack_from("f", read_bytes, offset + 8)[0]
                            bone_positions.append((x, y, z))
                        except:
                            bone_positions.append((0.0, 0.0, 0.0))

                    screen_positions = w2s_batch(view_matrix, bone_positions, self.window_width, self.window_height)

                    for b1, b2 in self.bone_connections:
                        if (b1 < len(screen_positions) and b2 < len(screen_positions)):
                            x1, y1 = screen_positions[b1]
                            x2, y2 = screen_positions[b2]
                            if (
                                -999 < x1 < self.window_width and -999 < y1 < self.window_height
                                and -999 < x2 < self.window_width and -999 < y2 < self.window_height
                                and 0 <= x1 <= self.window_width and 0 <= y1 <= self.window_height
                                and 0 <= x2 <= self.window_width and 0 <= y2 <= self.window_height
                            ):
                                self.bone_path.moveTo(x1, y1)
                                self.bone_path.lineTo(x2, y2)

                    xs = [p[0] for p in screen_positions if p[0] > 0 and p[1] > 0]
                    ys = [p[1] for p in screen_positions if p[0] > 0 and p[1] > 0]
                    if xs and ys:
                        min_x, max_x = min(xs), max(xs)
                        min_y, max_y = min(ys), max(ys)
                        width = max_x - min_x
                        height = max_y - min_y

                        dist = None
                        if local_pos is not None:
                            dx = local_pos[0] - bone_positions[0][0]
                            dy = local_pos[1] - bone_positions[0][1]
                            dz = local_pos[2] - bone_positions[0][2]
                            dist = math.sqrt(dx * dx + dy * dy + dz * dz)

                        players_to_draw.append(
                            {
                                "bbox": (min_x, min_y, width, height),
                                "health": health,
                                "name": player_name,
                                "weapon": weapon_name,
                                "center_bottom": ((min_x + max_x) / 2, max_y),
                                "distance": dist,
                            }
                        )

                except:
                    continue

        except:
            players_to_draw = []
            pass

        self.players_to_draw = players_to_draw
        self.update()

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        settings = get_current_settings()

        fps_to_show = int(self.game_fps) if self.game_fps > 0 else self.esp_fps
        watermark_text = f"FPS: {fps_to_show} | Made by Syfer-eng"

        painter.setPen(QtGui.QPen(QtGui.QColor(255, 255, 255, 200), 1))
        painter.setFont(self.font)
        painter.drawText(15, 25, watermark_text)

        if settings["esp_active"]:
            if settings.get("esp_show_skeleton_bones", True) and not self.bone_path.isEmpty() and settings.get("esp_color"):
                esp_color = QtGui.QColor(*settings["esp_color"])
                if self.esp_pen is None or self.esp_pen.color() != esp_color:
                    self.esp_pen = QtGui.QPen(esp_color, 2)
                painter.setPen(self.esp_pen)
                painter.drawPath(self.bone_path)

            if hasattr(self, "players_to_draw"):
                for player in self.players_to_draw:
                    if settings.get("mesh_enabled", False):
                        mesh_color = QtGui.QColor(*settings.get("mesh_color", (0, 255, 255, 128)))
                        if mesh_color.alpha() == 0:
                            mesh_color.setAlpha(128)
                        thickness = settings.get("mesh_thickness", 2)
                        pen = QtGui.QPen(mesh_color, thickness)
                        if settings.get("mesh_wireframe", True):
                            pen.setStyle(QtCore.Qt.PenStyle.SolidLine)
                        else:
                            pen.setStyle(QtCore.Qt.PenStyle.DashLine)
                        painter.setPen(pen)
                        painter.setBrush(QtCore.Qt.BrushStyle.NoBrush)
                        max_distance = settings.get("mesh_distance", 1500)
                        dist = player.get("distance", None)
                        if dist is not None and dist > max_distance:
                            continue
                        bx, by, bw, bh = player.get("bbox", (0, 0, 0, 0))
                        if bw > 5 and bh > 5:
                            painter.drawRect(int(bx), int(by), int(bw), int(bh))
                            rows = 4
                            cols = 4
                            for r in range(1, rows):
                                y_line = int(by + r * bh / rows)
                                painter.drawLine(int(bx), y_line, int(bx + bw), y_line)
                            for c in range(1, cols):
                                x_line = int(bx + c * bw / cols)
                                painter.drawLine(x_line, int(by), x_line, int(by + bh))
                            painter.drawLine(int(bx), int(by), int(bx + bw), int(by + bh))
                            painter.drawLine(int(bx + bw), int(by), int(bx), int(by + bh))

                    if settings.get("esp_show_box", True):
                        bx, by, bw, bh = player["bbox"]
                        box_color = QtGui.QColor(*settings.get("esp_box_color", (0, 255, 0, 255)))
                        if self.box_pen is None or self.box_pen.color() != box_color:
                            self.box_pen = QtGui.QPen(box_color, 2)
                        painter.setPen(self.box_pen)
                        painter.setBrush(QtCore.Qt.BrushStyle.NoBrush)
                        painter.drawRect(int(bx), int(by), int(bw), int(bh))

                    if settings.get("esp_show_health", True):
                        health = player["health"]
                        if health > 0:
                            bx, by, bw, bh = player["bbox"]
                            bar_height = int(bh * (health / 100))
                            bar_width = 5
                            bar_x = int(bx) - bar_width - 2
                            bar_y = int(by + bh - bar_height)

                            if settings.get("esp_health_gradient", True):
                                gradient = QtGui.QLinearGradient(bar_x, bar_y, bar_x, bar_y + bar_height)
                                gradient.setColorAt(0, QtGui.QColor(0, 255, 0, 180))
                                gradient.setColorAt(1, QtGui.QColor(255, 0, 0, 180))
                                painter.setPen(QtCore.Qt.PenStyle.NoPen)
                                painter.setBrush(gradient)
                                painter.drawRect(bar_x, bar_y, bar_width, bar_height)
                                painter.setBrush(QtGui.QColor(50, 50, 50, 150))
                                painter.drawRect(bar_x, int(by), bar_width, bh - bar_height)
                            else:
                                health_color = QtGui.QColor(*settings.get("esp_health_color", (255, 0, 0, 255)))
                                painter.setPen(QtCore.Qt.PenStyle.NoPen)
                                painter.setBrush(health_color)
                                painter.drawRect(bar_x, bar_y, bar_width, bar_height)
                                painter.setBrush(QtGui.QColor(50, 50, 50, 150))
                                painter.drawRect(bar_x, int(by), bar_width, bh - bar_height)

                    if settings.get("esp_show_name", True) and player.get("name", ""):
                        name = player["name"]
                        name_color = QtGui.QColor(*settings.get("esp_name_color", (255, 255, 255, 255)))
                        font_weight = (
                            QtGui.QFont.Weight.Bold if settings.get("esp_name_bold", True) else QtGui.QFont.Weight.Normal
                        )
                        font = QtGui.QFont("Arial", 12, font_weight)
                        painter.setFont(font)
                        painter.setPen(QtGui.QPen(name_color))

                        bx, by, bw, bh = player["bbox"]
                        text_width = painter.fontMetrics().horizontalAdvance(name)
                        x = int(bx + bw / 2 - text_width / 2)
                        y = int(by) - 5
                        painter.drawText(x, y, name)

                    if settings.get("esp_show_weapon_name", True) and player.get("weapon", ""):
                        weapon = player["weapon"]
                        weapon_color = QtGui.QColor(*settings.get("esp_weapon_color", (255, 255, 0, 255)))
                        painter.setFont(QtGui.QFont("Arial", 10, QtGui.QFont.Weight.Normal))
                        painter.setPen(QtGui.QPen(weapon_color))

                        bx, by, bw, bh = player["bbox"]
                        text_width = painter.fontMetrics().horizontalAdvance(weapon)
                        x = int(bx + bw / 2 - text_width / 2)
                        y = int(by) + bh + 15
                        painter.drawText(x, y, weapon)

                    if settings.get("esp_show_distance", True) and player.get("distance", None) is not None:
                        dist = player["distance"]
                        dist_text = f"{int(dist)}m"
                        dist_color = QtGui.QColor(200, 200, 255, 255)
                        painter.setFont(QtGui.QFont("Arial", 9, QtGui.QFont.Weight.Normal))
                        painter.setPen(QtGui.QPen(dist_color))

                        bx, by, bw, bh = player["bbox"]
                        text_width = painter.fontMetrics().horizontalAdvance(dist_text)
                        x = int(bx + bw / 2 - text_width / 2)
                        y = int(by) - 20
                        painter.drawText(x, y, dist_text)

        if settings.get("fov_show", True) and settings.get("aim_active", False):
            width, height = self.window_width, self.window_height
            crosshair_x, crosshair_y = width // 2, height // 2

            if self.dwClientState != 0 and self.dwClientState_ViewAngles != 0:
                try:
                    client_state = self.pm.read_int(self.dwClientState)
                    if client_state:
                        pitch = self.pm.read_float(client_state + self.dwClientState_ViewAngles)
                        yaw = self.pm.read_float(client_state + self.dwClientState_ViewAngles + 0x4)

                        pitch_rad = math.radians(pitch)
                        yaw_rad = math.radians(yaw)

                        forward_x = math.cos(pitch_rad) * math.cos(yaw_rad)
                        forward_y = math.cos(pitch_rad) * math.sin(yaw_rad)
                        forward_z = math.sin(pitch_rad)

                        camera_pos = (0, 0, 0)
                        world_pos = (
                            camera_pos[0] + forward_x * 1000,
                            camera_pos[1] + forward_y * 1000,
                            camera_pos[2] + forward_z * 1000,
                        )

                        view_matrix = [self.pm.read_float(self.client + self.dwViewMatrix + i * 4) for i in range(16)]
                        proj_x, proj_y = w2s_batch(view_matrix, [world_pos], width, height)[0]

                        if 0 <= proj_x <= width and 0 <= proj_y <= height:
                            crosshair_x, crosshair_y = proj_x, proj_y
                except:
                    pass

            radius = settings["aim_radius"] / 100 * min(width, height) / 2

            for i in range(3):
                alpha = 30 - (i * 10)
                glow_color = QtGui.QColor(*settings["fov_color"][:3], alpha)
                glow_pen = QtGui.QPen(glow_color, 3 - i)
                painter.setPen(glow_pen)
                painter.setBrush(QtCore.Qt.BrushStyle.NoBrush)
                painter.drawEllipse(
                    int(crosshair_x - radius - i),
                    int(crosshair_y - radius - i),
                    int((radius + i) * 2),
                    int((radius + i) * 2),
                )

            fov_color = QtGui.QColor(*settings["fov_color"])
            fov_pen = QtGui.QPen(fov_color, 1)
            painter.setPen(fov_pen)
            painter.drawEllipse(
                int(crosshair_x - radius),
                int(crosshair_y - radius),
                int(radius * 2),
                int(radius * 2),
            )

        if settings.get("rainbow_pinwheel", False):
            t = time.time()
            center_x, center_y = self.window_width // 2, self.window_height // 2
            arm_length = 40
            num_arms = 8
            rotation_speed = 1.5
            angle_offset = t * rotation_speed

            for i in range(num_arms):
                angle = angle_offset + (2 * math.pi / num_arms) * i
                r = int((math.sin(angle) + 1) * 127)
                g = int((math.sin(angle + 2) + 1) * 127)
                b = int((math.sin(angle + 4) + 1) * 127)
                pen = QtGui.QPen(QtGui.QColor(r, g, b), 3)
                painter.setPen(pen)

                x = center_x + math.cos(angle) * arm_length
                y = center_y + math.sin(angle) * arm_length
                painter.drawLine(center_x, center_y, int(x), int(y))

        painter.end()

class MenuToggleHandler:
    def __init__(self, settings_menu):
        self.settings_menu = settings_menu
        self.insert_pressed = False
        self.last_insert_time = 0

    def check_toggle(self):
        current_time = time.time()
        insert_state = win32api.GetAsyncKeyState(win32con.VK_INSERT) & 0x8000

        if insert_state and not self.insert_pressed:
            if current_time - self.last_insert_time > 0.3:
                self.toggle_menu()
                self.last_insert_time = current_time
            self.insert_pressed = True
        elif not insert_state:
            self.insert_pressed = False

    def toggle_menu(self):
        if self.settings_menu.isVisible():
            self.settings_menu.hide()
        else:
            self.settings_menu.show()
            self.settings_menu.raise_()
            self.settings_menu.activateWindow()

CURRENT_VERSION = "1.0.8"  # Change this for new releases


def check_for_update_decision():
    try:
        url = "https://raw.githubusercontent.com/Skeleton-Archive/cs2-offsets/refs/heads/main/Versions.json"
        response = requests.get(url, timeout=5)
        data = response.json()

        latest = data.get("latest_version", CURRENT_VERSION)
        links = data.get("download_links", {})
        download_url = links.get(latest)

        if latest != CURRENT_VERSION and download_url:
            box = QMessageBox()
            box.setWindowTitle("Update Available")
            box.setText(f"A new version ({latest}) is available.\nDo you want to update?")
            box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            box.setDefaultButton(QMessageBox.StandardButton.Yes)
            result = box.exec()

            if result == QMessageBox.StandardButton.Yes:
                webbrowser.open(download_url)
                sys.exit(0)
    except Exception as e:
        print(f"[Update Check] Error: {e}")


if __name__ == "__main__":
    app = QApplication(sys.argv)

    check_for_update_decision()

    print("Waiting for cs2.exe...")
    while True:
        try:
            pm = pymem.Pymem("cs2.exe")
            client = pymem.process.module_from_name(pm.process_handle, "client.dll").lpBaseOfDll
            break
        except:
            time.sleep(1)

    print("Downloading offsets...")
    offsets, client_dll = get_offsets_and_client_dll()

    if not offsets or not client_dll:
        print("Failed to download offsets.")
        input("Press Enter to exit...")
        sys.exit(1)

    print("Syfer-eng")

    def monitor_process():
        while True:
            if not any(p.name().lower() == "cs2.exe" for p in psutil.process_iter(['name'])):
                print("cs2 not running. Exiting.")
                os._exit(0)
            time.sleep(2)

    threading.Thread(target=monitor_process, daemon=True).start()
    threading.Thread(target=aimbot_thread, args=(pm, client, offsets, client_dll), daemon=True).start()

    try:
        settings_menu = SettingsMenu()
        esp_window = FastBoneESPWindow(pm, offsets, client_dll)
        esp_window.show()
        settings_menu.show()

        menu_handler = MenuToggleHandler(settings_menu)
        menu_timer = QtCore.QTimer()
        menu_timer.timeout.connect(menu_handler.check_toggle)
        menu_timer.start(50)

        sys.exit(app.exec())
    except Exception as e:
        print(f"Error starting: {e}")
        input("Press Enter to exit...")
        sys.exit(1)