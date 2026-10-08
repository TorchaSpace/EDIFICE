import sys

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

from edifice.service import Project
from edifice.ui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    font = QFont("SF Pro Display", 12)
    font.setStyleStrategy(QFont.PreferAntialias)
    app.setFont(font)
    win = MainWindow(Project.mock())
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
