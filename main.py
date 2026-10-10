import sys

from PySide6.QtGui import QColor, QFont, QPalette
from PySide6.QtWidgets import QApplication

from edifice.db import Store
from edifice.ui.main_window import MainWindow


def main():
    selftest = "--selftest" in sys.argv
    app = QApplication(sys.argv)
    from pathlib import Path
    from PySide6.QtGui import QFontDatabase
    import edifice
    for f in sorted((Path(edifice.__file__).parent / "assets" / "fonts").glob("*.ttf")):   # Manrope + DM Mono (SIL OFL)
        QFontDatabase.addApplicationFont(str(f))
    font = QFont("Manrope", 12)
    font.setStyleStrategy(QFont.PreferAntialias | QFont.PreferQuality)
    font.setHintingPreference(QFont.PreferNoHinting)
    app.setFont(font)
    # Figma tasarımının koyu teması (sistem temasından bağımsız)
    pal = QPalette()
    for role, color in ((QPalette.Window, "#070C12"), (QPalette.Base, "#0B1624"),
                        (QPalette.AlternateBase, "#070C12"), (QPalette.Text, "#E8F2FF"),
                        (QPalette.WindowText, "#E8F2FF"), (QPalette.ButtonText, "#E8F2FF"),
                        (QPalette.Button, "#0B1624"), (QPalette.ToolTipBase, "#05080E"),
                        (QPalette.ToolTipText, "#E8F2FF"), (QPalette.HighlightedText, "#E8F2FF")):
        pal.setColor(role, QColor(color))
    pal.setColor(QPalette.PlaceholderText, QColor("#6E849B"))
    pal.setColor(QPalette.Highlight, QColor(13, 221, 150, 40))
    app.setPalette(pal)
    from edifice import safety
    from edifice.db import default_path
    from PySide6.QtWidgets import QMessageBox
    safety.install_crash_log(lambda msg: QMessageBox.warning(None, "EDIFI'CE", msg))
    path = default_path()
    note = None if selftest else safety.recover_if_corrupt(path)      # bozuk veritabanı: yedekten kurtar
    if not selftest:
        try:
            safety.backup_db(path)                                    # günlük otomatik yedek (en son 7)
        except Exception:
            safety.LOG.exception("Yedek alınamadı")
    store = Store()
    if note:
        QMessageBox.information(None, "EDIFI'CE", note)
    if store.count() == 0:
        store.seed_demo()
    win = MainWindow(store.load_project(store.latest_id()), store)
    win.show()
    if selftest:   # paketleme sonrası hızlı sağlık kontrolü: pencere kurulur, tüm sayfalar açılır, çıkılır
        for i in range(len(win.pages)):
            win.select(i)
            app.processEvents()
        import tempfile
        from pathlib import Path
        from edifice.excel_io import build_template, read_workbook
        from edifice.ui.report_pdf import build_pdf
        from PySide6.QtGui import QFontDatabase
        assert {"Manrope", "DM Mono"} <= set(QFontDatabase.families()), "gömülü yazı tipleri yüklenmedi"
        import numpy as _np                                   # hava/M&V motoru numpy ister: paketlenmiş uygulamada da çalışmalı
        from datetime import date as _d, timedelta as _td
        from edifice import weather as _w
        from edifice.engine.weather_norm import normalize as _norm
        from edifice.geocode import parse as _gparse          # QtNetwork/JSON yolları
        from edifice.solar import parse_pvgis as _pv
        assert _np.__version__ and _gparse(b"{}") == [] and _pv(b"{}") is None
        daily = [(_d(2013, 1, 1) + _td(days=i), 14 - 10 * _np.cos(2 * _np.pi * (i % 365 - 15) / 365)) for i in range(365 * 14)]
        dd = _w.monthly_degree_days(daily)
        assert _norm(win.project, dd) is not None
        with tempfile.TemporaryDirectory() as d:        # Excel şablonu + içe aktarma + PDF paketli uygulamada da çalışmalı
            xlsx = build_template(str(Path(d) / "t.xlsx"), example=True)
            read_workbook(xlsx)
            pdf = build_pdf(win.project, [], str(Path(d) / "r.pdf"))
            assert Path(pdf).stat().st_size > 5000
        print("EDIFICE selftest OK")
        sys.exit(0)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
