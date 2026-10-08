"""docs/KAYNAKCA.md dosyasını kanıt kaydından üretir. Kullanım: python tools/make_docs.py"""
import sys
from pathlib import Path

root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))
from edifice.evidence import render_markdown  # noqa: E402
from edifice.models import Assumptions  # noqa: E402

(root / "docs").mkdir(exist_ok=True)
(root / "docs" / "KAYNAKCA.md").write_text(render_markdown(Assumptions()), encoding="utf-8")
print("docs/KAYNAKCA.md yazıldı")
