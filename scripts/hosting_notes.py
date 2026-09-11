"""Baca username & password akun hosting (DirectAdmin) dari catatan project manager.

Catatan dibuat PM di folder Drive: /home/On Progress/<domain>/<domain>.txt, dengan
bagian "WEB & CPANEL" berisi baris `username:` dan `password:`. Password akun ini
juga dipakai sebagai password admin WordPress, supaya login situs sesuai catatan.

Dulu installer memakai satu file password bersama untuk semua situs, sehingga
login WordPress tidak pernah cocok dengan catatan (2026-09-11).

Nilai kredensial TIDAK boleh dicetak ke log atau terminal.
"""
import re
from pathlib import Path

ON_PROGRESS = Path('/home/On Progress')
USER_RE = re.compile(r'^\s*(?:user ?name|user|login)\s*[:=]\s*(.*)$', re.I)
PASS_RE = re.compile(r'^\s*(?:pass(?:word)?|sandi|pw)\s*[:=]\s*(.*)$', re.I)


def read_hosting_notes(domain):
    """(username, password) dari catatan hosting; string kosong kalau tidak ada.

    Hanya baris berlabel yang dipercaya: bagian atas catatan berisi baris tanpa
    label (email, kata sandi lain) yang bukan login akun hosting."""
    path = ON_PROGRESS / domain / f'{domain}.txt'
    try:
        lines = path.read_text(errors='replace').splitlines()
    except OSError:
        return '', ''
    user = password = ''
    for i, line in enumerate(lines):
        # Nilai kadang ditulis di baris berikutnya, tapi jangan sampai mengambil
        # baris label lain.
        nxt = next((x.strip() for x in lines[i + 1:i + 3] if x.strip()), '')
        if USER_RE.match(nxt) or PASS_RE.match(nxt) or ':' in nxt:
            nxt = ''
        m = USER_RE.match(line)
        if m:
            user = m.group(1).strip() or nxt
        m = PASS_RE.match(line)
        if m:
            password = m.group(1).strip() or nxt
    return re.sub(r'[^a-z0-9]', '', user.lower()), password
