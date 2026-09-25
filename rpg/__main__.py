# -*- coding: utf-8 -*-
"""Jalankan permainan di jendela sendiri:  python3 -m rpg [--window]"""

import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if HERE not in sys.path:
    sys.path.insert(0, HERE)            # agar sounds.py & activities.py ikut dipakai

from PyQt5.QtCore import Qt             # noqa: E402
from PyQt5.QtGui import QIcon           # noqa: E402
from PyQt5.QtWidgets import QApplication  # noqa: E402

from rpg.data import GAME_TITLE         # noqa: E402
from rpg.game import RpgGame            # noqa: E402


def main():
    app = QApplication(sys.argv)
    app.setApplicationName(GAME_TITLE)
    game = RpgGame(standalone=True)
    game.setWindowTitle(GAME_TITLE)
    game.exit_requested.connect(app.quit)
    if "--window" in sys.argv:
        game.resize(960, 720)
        game.show()
    else:
        game.showFullScreen()
    game.start()
    code = app.exec_()
    game.shutdown()
    try:
        import sounds
        sounds.shutdown()
    except Exception:
        pass
    sys.exit(code)


if __name__ == "__main__":
    main()
