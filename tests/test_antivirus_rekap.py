"""Rekap antivirus: dipakai ulang selama sumber sama, dihitung ulang saat sumber berubah. python3 tests/test_antivirus_rekap.py"""
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'services'))
import installer_status as ist  # noqa: E402

with tempfile.TemporaryDirectory() as d:
    akar = Path(d)
    (akar / 'scan').mkdir()
    ist.ANTIVIRUS_DIR = akar
    ist.ANTIVIRUS_REKAP = akar / 'rekap'
    ist.ANTIVIRUS_AMAN = akar / 'aman.json'
    ist.ANTIVIRUS_AMAN.write_text('{}')
    hitung = []

    def h():
        hitung.append(1)
        return {'n': len(hitung)}

    assert ist._rekap('x', h) == {'n': 1}
    assert ist._rekap('x', h) == {'n': 1}, 'sumber sama: pakai rekap tersimpan'
    os.utime(ist.ANTIVIRUS_AMAN, (1, 1))
    assert ist._rekap('x', h) == {'n': 2}, 'aman.json berubah: hitung ulang'
    (akar / 'scan' / 'a.json').write_text('{}')
    assert ist._rekap('x', h) == {'n': 3}, 'scan baru: hitung ulang'
print('ok')
