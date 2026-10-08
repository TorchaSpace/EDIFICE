import sys

from PySide6.QtGui import QColor, QFont, QPalette
from PySide6.QtWidgets import QApplication

from edifice.db import Store
from edifice.ui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    font = QFont("Manrope", 12)
    font.setStyleStrategy(QFont.PreferAntialias)
    app.setFont(font)
    # Figma tasarımının koyu teması (sistem temasından bağımsız)
    pal = QPalette()
    for role, color in ((QPalette.Window, "#070C12"), (QPalette.Base, "#0B1624"),
                        (QPalette.AlternateBase, "#070C12"), (QPalette.Text, "#E8F2FF"),
                        (QPalette.WindowText, "#E8F2FF"), (QPalette.ButtonText, "#E8F2FF"),
                        (QPalette.Button, "#0B1624"), (QPalette.ToolTipBase, "#05080E"),
                        (QPalette.ToolTipText, "#E8F2FF")):
        pal.setColor(role, QColor(color))
    app.setPalette(pal)
    store = Store()
    if store.count() == 0:
        store.seed_demo()
    win = MainWindow(store.load_project(store.latest_id()), store)
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
