import sys

from PySide6.QtGui import QColor, QFont, QPalette
from PySide6.QtWidgets import QApplication

from edifice.service import Project
from edifice.ui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    font = QFont("SF Pro Display", 12)
    font.setStyleStrategy(QFont.PreferAntialias)
    app.setFont(font)
    # Sistem koyu temadayken bile açık tema renkleri kullanılsın
    pal = QPalette()
    for role, color in ((QPalette.Window, "#F5F4F0"), (QPalette.Base, "#FFFFFF"),
                        (QPalette.AlternateBase, "#F5F4F0"), (QPalette.Text, "#0E2A24"),
                        (QPalette.WindowText, "#0E2A24"), (QPalette.ButtonText, "#0E2A24"),
                        (QPalette.Button, "#FFFFFF")):
        pal.setColor(role, QColor(color))
    app.setPalette(pal)
    win = MainWindow(Project.mock())
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
