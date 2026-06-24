# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 masioware
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""Pressure Monitor Plugin for Krita — reads pen pressure via QTabletEvent."""

from krita import Krita, DockWidget, DockWidgetFactory, DockWidgetFactoryBase
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QProgressBar, QSizePolicy, QFrame, QPushButton, QApplication,
)
from PyQt5.QtCore import Qt, QTimer, QObject, QEvent
from PyQt5.QtGui import QPainter, QColor, QPen, QBrush, QFont
import math


class TabletEventFilter(QObject):
    """Application-level event filter that reads pen pressure from QTabletEvents."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.pressure = 0.0
        self._app = QApplication.instance()
        self._app.installEventFilter(self)

    def eventFilter(self, obj, event):
        if event.type() in (QEvent.TabletPress, QEvent.TabletMove, QEvent.TabletRelease):
            try:
                self.pressure = max(0.0, min(1.0, float(event.pressure())))
            except Exception:
                pass
        return False

    def uninstall(self):
        try:
            self._app.removeEventFilter(self)
        except Exception:
            pass


class PressureGauge(QWidget):
    """Circular arc gauge with sparkline history and peak marker."""

    _ARC_START = 220
    _ARC_SPAN  = -260

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pressure  = 0.0
        self._peak      = 0.0
        self._history   = []
        self._history_max = 80
        self.setMinimumSize(140, 140)
        self.setMaximumHeight(210)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def set_pressure(self, value: float):
        self._pressure = value = max(0.0, min(1.0, value))
        if value > self._peak:
            self._peak = value
        self._history.append(value)
        if len(self._history) > self._history_max:
            self._history.pop(0)
        self.update()

    def reset_peak(self):
        self._peak = 0.0
        self.update()

    def _color(self, p: float) -> QColor:
        """Blue → purple → red gradient mapped to pressure 0-1."""
        if p < 0.33:
            t = p / 0.33
            return QColor(int(60 + t*60), int(180 + t*20), 255)
        if p < 0.66:
            t = (p - 0.33) / 0.33
            return QColor(int(120 + t*135), int(200 - t*100), int(255 - t*205))
        t = (p - 0.66) / 0.34
        return QColor(255, int(100 - t*70), int(50 - t*30))

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w, h   = self.width(), self.height()
        size   = min(w, h)
        cx, cy = w / 2, h / 2
        r      = size * 0.37
        ax, ay = cx - r, cy - r
        aw     = r * 2
        start, span = self._ARC_START, self._ARC_SPAN

        self._draw_sparkline(painter, w, h)

        painter.setPen(QPen(QColor(40, 40, 58), int(size * 0.065), Qt.SolidLine, Qt.RoundCap))
        painter.drawArc(int(ax), int(ay), int(aw), int(aw), start * 16, span * 16)

        if self._pressure > 0.002:
            painter.setPen(QPen(self._color(self._pressure), int(size * 0.065), Qt.SolidLine, Qt.RoundCap))
            painter.drawArc(int(ax), int(ay), int(aw), int(aw), start * 16, int(span * self._pressure) * 16)

        if self._peak > 0.002:
            ang = math.radians(start + span * self._peak)
            px, py = cx + r * math.cos(ang), cy - r * math.sin(ang)
            painter.setPen(QPen(QColor(255, 225, 60), 2))
            painter.setBrush(QBrush(QColor(255, 225, 60)))
            painter.drawEllipse(int(px - 4), int(py - 4), 8, 8)

        painter.setFont(QFont("Monospace", int(size * 0.22), QFont.Bold))
        painter.setPen(self._color(self._pressure))
        painter.drawText(int(cx - size*0.3), int(cy - size*0.22),
                         int(size*0.6), int(size*0.38),
                         Qt.AlignHCenter | Qt.AlignVCenter, str(int(self._pressure * 100)))

        painter.setFont(QFont("Monospace", int(size * 0.10)))
        painter.setPen(QColor(110, 110, 145))
        painter.drawText(int(cx - size*0.3), int(cy + size*0.1),
                         int(size*0.6), int(size*0.18),
                         Qt.AlignHCenter | Qt.AlignVCenter, "%")

        painter.end()

    def _draw_sparkline(self, painter: QPainter, w: int, h: int):
        if len(self._history) < 2:
            return
        sh   = h * 0.22
        sb   = h - 3
        step = w / (self._history_max - 1)
        for i in range(len(self._history) - 1):
            c = self._color(self._history[i])
            c.setAlpha(100)
            painter.setPen(QPen(c, 1.5))
            painter.drawLine(
                int(i * step),       int(sb - self._history[i]     * sh),
                int((i+1) * step),   int(sb - self._history[i + 1] * sh),
            )


class PressureMonitorWidget(QWidget):
    """Docker panel: gauge, live bar, RAW / PEAK / AVG cards and reset button."""

    _STYLESHEET = """
        QWidget          { color:#b0b0c8; font-family:monospace; }
        QFrame#card      { border-radius:6px; }
        QLabel#sec       { color:#484868; font-size:9px; letter-spacing:2px; }
        QLabel#val       { color:#90b8ff; font-size:12px; font-weight:bold; }
        QPushButton      { border:none; color:#383858; padding:4px; font-size:10px; }
        QPushButton:hover{ color:#7878a8; }
    """
    _BAR_STYLESHEET = """
        QProgressBar        { border-radius:3px; border:none; }
        QProgressBar::chunk { border-radius:3px;
                              background:qlineargradient(x1:0,y1:0,x2:1,y2:0,
                                stop:0 #40beff, stop:0.5 #9050ff, stop:1 #ff4444); }
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._filter      = TabletEventFilter()
        self._decay_steps = 0
        self._avg_samples = []
        self._setup_ui()
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._update)
        self._timer.start(30)

    def _setup_ui(self):
        self.setStyleSheet(self._STYLESHEET)

        root = QVBoxLayout(self)
        root.setContentsMargins(8, 6, 8, 6)
        root.setSpacing(4)

        self.gauge = PressureGauge()
        root.addWidget(self.gauge)

        self.bar = QProgressBar()
        self.bar.setRange(0, 1000)
        self.bar.setValue(0)
        self.bar.setTextVisible(False)
        self.bar.setFixedHeight(6)
        self.bar.setStyleSheet(self._BAR_STYLESHEET)
        root.addWidget(self.bar)

        row = QHBoxLayout()
        row.setSpacing(4)
        self._lbl_raw  = self._card(row, "RAW",  "0.000")
        self._lbl_peak = self._card(row, "PEAK", "0.000")
        self._lbl_avg  = self._card(row, "AVG",  "0.000")
        root.addLayout(row)

        btn = QPushButton("↺ RESET PEAK")
        btn.clicked.connect(self._reset_peak)
        btn.setFixedHeight(22)
        root.addWidget(btn)
        root.addStretch()

    def _card(self, layout, title: str, init: str) -> QLabel:
        frame = QFrame()
        frame.setObjectName("card")
        col = QVBoxLayout(frame)
        col.setContentsMargins(6, 4, 6, 4)
        col.setSpacing(1)
        lbl_title = QLabel(title)
        lbl_title.setObjectName("sec")
        lbl_title.setAlignment(Qt.AlignCenter)
        col.addWidget(lbl_title)
        lbl_val = QLabel(init)
        lbl_val.setObjectName("val")
        lbl_val.setAlignment(Qt.AlignCenter)
        col.addWidget(lbl_val)
        layout.addWidget(frame)
        return lbl_val

    def _update(self):
        raw = self._filter.pressure
        if raw > 0.001:
            self._decay_steps = 10
            display = raw
            self._avg_samples.append(raw)
            if len(self._avg_samples) > 80:
                self._avg_samples.pop(0)
        elif self._decay_steps > 0:
            self._decay_steps -= 1
            display = self.gauge._pressure * 0.7
        else:
            display = 0.0

        self.gauge.set_pressure(display)
        self.bar.setValue(int(display * 1000))
        self._lbl_raw.setText(f"{raw:.3f}")
        self._lbl_peak.setText(f"{self.gauge._peak:.3f}")
        avg = sum(self._avg_samples) / len(self._avg_samples) if self._avg_samples else 0.0
        self._lbl_avg.setText(f"{avg:.3f}")

    def _reset_peak(self):
        self.gauge.reset_peak()
        self._avg_samples.clear()

    def closeEvent(self, event):
        self._filter.uninstall()
        super().closeEvent(event)


class PressureMonitorDocker(DockWidget):
    """Krita DockWidget host for the pressure monitor panel."""

    title = "Pressure Monitor"

    def __init__(self):
        super().__init__()
        self.setWindowTitle(self.title)
        self.setWidget(PressureMonitorWidget(self))

    def canvasChanged(self, canvas):
        pass


Krita.instance().addDockWidgetFactory(
    DockWidgetFactory("pressure_monitor", DockWidgetFactoryBase.DockRight, PressureMonitorDocker)
)
