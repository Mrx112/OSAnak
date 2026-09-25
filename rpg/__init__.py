# -*- coding: utf-8 -*-
"""
Legenda Kristal Pelangi: RPG petualangan 2D untuk KidsOS.

  * kidsos:rpg      -> dibuka dari menu anak (RpgActivity, di dalam launcher)
  * python3 -m rpg  -> jendela sendiri (mis. dari Desktop Admin / kidsos-rpg)

Main sendiri atau bersama teman lewat LAN (lobi di Kedai Petualang, maksimal
4 pemain). Tidak butuh internet maupun file gambar/suara tambahan.
"""

from PyQt5.QtCore import QTimer

from .game import RpgGame

__all__ = ["RpgGame", "RpgActivity"]


_ACTIVITY_CLASS = None


def _activity_class():
    """Dibuat saat pertama dipakai: activities.py hanya ada di dalam KidsOS."""
    global _ACTIVITY_CLASS
    if _ACTIVITY_CLASS is not None:
        return _ACTIVITY_CLASS
    from activities import Activity

    class _RpgActivity(Activity):
        MUSIC = None            # musik diatur sendiri oleh permainan

        def __init__(self, scale, parent=None):
            super().__init__("🏰 Legenda Kristal Pelangi", scale, parent)
            # Layar penuh untuk permainan: sembunyikan bar atas aktivitas.
            for w in (self.home_btn, self.up_btn, self.title, self.stars):
                w.hide()
            bar = self.home_btn.parentWidget()
            if bar is not None and bar is not self:
                bar.hide()
            self.layout().setSpacing(0)
            self.game = RpgGame(self)
            self.game.exit_requested.connect(self.exit_requested.emit)
            self.pages.addWidget(self.game)
            self.game.start()
            QTimer.singleShot(0, self.game.setFocus)

        def closing(self):
            self.game.shutdown()
            super().closing()

    _ACTIVITY_CLASS = _RpgActivity
    return _ACTIVITY_CLASS


def RpgActivity(scale, parent=None):
    """Aktivitas KidsOS (kidsos:rpg) berisi permainan."""
    return _activity_class()(scale, parent)
