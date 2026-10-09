"""Bangun berkas Word "Rangkuman Website Konsep" dari rangkuman.json (hasil `laravel-brief <id> rangkuman`).

Template = templates/laravel/rangkuman-konsep.docx: gaya, huruf, ukuran halaman, dan margin dari
"Rangkuman Website Konsep SIMONTAK RSUD Piru.docx" (buatan PM, dipilih user 2026-09-30) dengan badan dikosongkan.
Susunan mengikuti dokumen itu: judul tebal, paragraf pembuka, bagian bernomor 1–7 (Peran User, Fungsi Website,
Menu web dan isinya, Tambahan Fitur, Desain Website, Warna Website, Batasan Sistem) lalu "Catatan Teknis:".
Tiap bagian = kelompok (subjudul opsional + poin "- ...") dipisah paragraf kosong. Gambar klien (dokumen unggahan
jenis gambar) disisipkan di bagian Desain, rata tengah dengan keterangan miring, seperti infografis di contoh.
"""
import io
import re
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from xml.sax.saxutils import escape

TEMPLATE = Path(__file__).resolve().parent.parent / 'templates' / 'laravel' / 'rangkuman-konsep.docx'
LEBAR_MAKS_EMU = 5943600          # lebar isi halaman (6,5 inci), sama dengan gambar di contoh
TINGGI_MAKS_EMU = 7315200         # 8 inci supaya gambar potret tetap muat satu halaman
GAMBAR_MAKS = 6
BAGIAN = (('peran', 'Peran User'), ('fungsi', 'Fungsi Website'), ('menu', 'Menu web dan isinya'),
          ('tambahan_fitur', 'Tambahan Fitur'), ('desain', 'Desain Website'), ('warna', 'Warna Website'),
          ('batasan', 'Batasan Sistem'))


def _p(teks='', tebal=False, miring=False, tengah=False):
    if not teks:
        return '<w:p/>'
    rpr = ('<w:b/><w:bCs/>' if tebal else '') + ('<w:i/><w:iCs/>' if miring else '')
    rpr = f'<w:rPr>{rpr}</w:rPr>' if rpr else ''
    ppr = ('<w:jc w:val="center"/>' if tengah else '') + rpr
    ppr = f'<w:pPr>{ppr}</w:pPr>' if ppr else ''
    return f'<w:p>{ppr}<w:r>{rpr}<w:t xml:space="preserve">{escape(teks)}</w:t></w:r></w:p>'


def _poin(teks):
    teks = re.sub(r'^\s*[-•*–]\s*', '', str(teks)).strip()
    return _p(f'- {teks}') if teks else ''


def _kelompok(daftar):
    """[{subjudul, poin[]}] → paragraf, kelompok dipisah paragraf kosong."""
    hasil = []
    for k in daftar or []:
        if isinstance(k, str):
            k = {'subjudul': '', 'poin': [k]}
        isi = [_p(str(k.get('subjudul') or '').strip())] if str(k.get('subjudul') or '').strip() else []
        isi += [x for x in map(_poin, k.get('poin') or []) if x]
        if isi:
            if hasil:
                hasil.append(_p())
            hasil += isi
    return hasil


def _gambar(rid, nomor, nama, lebar_px, tinggi_px):
    cx = LEBAR_MAKS_EMU
    cy = int(cx * tinggi_px / max(lebar_px, 1))
    if cy > TINGGI_MAKS_EMU:
        cx, cy = int(cx * TINGGI_MAKS_EMU / cy), TINGGI_MAKS_EMU
    nama = escape(nama, {'"': '&quot;'})
    return (
        '<w:p><w:pPr><w:jc w:val="center"/></w:pPr><w:r><w:rPr><w:noProof/></w:rPr><w:drawing>'
        f'<wp:inline distT="0" distB="0" distL="0" distR="0"><wp:extent cx="{cx}" cy="{cy}"/>'
        f'<wp:effectExtent l="0" t="0" r="0" b="0"/><wp:docPr id="{nomor}" name="{nama}"/>'
        '<wp:cNvGraphicFramePr><a:graphicFrameLocks xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" noChangeAspect="1"/></wp:cNvGraphicFramePr>'
        '<a:graphic xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture">'
        f'<pic:pic xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture"><pic:nvPicPr><pic:cNvPr id="{nomor}" name="{nama}"/><pic:cNvPicPr/></pic:nvPicPr>'
        f'<pic:blipFill><a:blip r:embed="{rid}"/><a:stretch><a:fillRect/></a:stretch></pic:blipFill>'
        f'<pic:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr>'
        '</pic:pic></a:graphicData></a:graphic></wp:inline></w:drawing></w:r></w:p>'
    )


def _siapkan_gambar(path):
    """-> (bytes PNG/JPEG, ekstensi, lebar, tinggi) atau None. WebP/GIF/RGBA-JPEG diubah ke PNG."""
    try:
        from PIL import Image
        with Image.open(path) as im:
            im.load()
            lebar, tinggi = im.size
            if im.format == 'JPEG':
                return Path(path).read_bytes(), 'jpeg', lebar, tinggi
            if im.format == 'PNG':
                return Path(path).read_bytes(), 'png', lebar, tinggi
            buf = io.BytesIO()
            im.convert('RGBA' if im.mode in ('RGBA', 'LA', 'P') else 'RGB').save(buf, 'PNG')
            return buf.getvalue(), 'png', lebar, tinggi
    except Exception:  # noqa: BLE001 — gambar rusak cukup dilewati
        return None


def bangun(data, gambar=(), keluar=None):
    """data = rangkuman.json; gambar = [(path, keterangan)]. Mengembalikan bytes .docx (dan menulis ke `keluar`)."""
    with zipfile.ZipFile(TEMPLATE) as z:
        berkas = {n: z.read(n) for n in z.namelist()}
    dok = berkas['word/document.xml'].decode()
    kepala, ekor = dok[:dok.index('<w:body>') + 8], dok[dok.index('<w:sectPr'):]
    rels = berkas['word/_rels/document.xml.rels'].decode()
    tipe = berkas['[Content_Types].xml'].decode()

    isi = [_p(str(data.get('judul') or 'Rangkuman Website Konsep').strip(), tebal=True)]
    if str(data.get('pembuka') or '').strip():
        isi.append(_p(str(data['pembuka']).strip()))
    media = {}
    for no, (kunci, label) in enumerate(BAGIAN, 1):
        isi += [_p(), _p(f'{no}. {label}')]
        if kunci == 'desain':
            d = data.get('desain') or {}
            if str(d.get('pembuka') or '').strip():
                isi.append(_p(str(d['pembuka']).strip()))
            for i, (path, ket) in enumerate(list(gambar)[:GAMBAR_MAKS], 1):
                g = _siapkan_gambar(path)
                if not g:
                    continue
                bytes_, ext, lebar, tinggi = g
                rid = f'rIdRangkuman{i}'
                media[f'word/media/rangkuman{i}.{ext}'] = bytes_
                rels = rels.replace('</Relationships>', f'<Relationship Id="{rid}" Type="http://schemas.openxmlformats.org/'
                                    f'officeDocument/2006/relationships/image" Target="media/rangkuman{i}.{ext}"/></Relationships>')
                if f'Extension="{ext}"' not in tipe:
                    tipe = tipe.replace('<Default Extension="rels"', f'<Default Extension="{ext}" ContentType="image/{ext}"/>'
                                        '<Default Extension="rels"')
                isi += [_p(), _gambar(rid, 100 + i, Path(path).name, lebar, tinggi), _p(ket, miring=True, tengah=True)]
            poin = _kelompok([{'subjudul': '', 'poin': d.get('poin') or []}])
            if poin:
                isi += [_p()] + poin
        else:
            nilai = data.get(kunci) or []
            isi += _kelompok(nilai if nilai and isinstance(nilai[0], dict) else [{'subjudul': '', 'poin': nilai}])
    catatan = [x for x in map(_poin, data.get('catatan_teknis') or []) if x]
    if catatan:
        isi += [_p(), _p('Catatan Teknis:')] + catatan

    berkas['word/document.xml'] = (kepala + ''.join(isi) + ekor).encode()
    berkas['word/_rels/document.xml.rels'] = rels.encode()
    berkas['[Content_Types].xml'] = tipe.encode()
    waktu = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    core = berkas['docProps/core.xml'].decode()
    core = re.sub(r'<dc:title>[^<]*</dc:title>', f'<dc:title>{escape(str(data.get("judul") or ""))}</dc:title>', core)
    core = re.sub(r'(<dcterms:(created|modified) xsi:type="dcterms:W3CDTF">)[^<]*', rf'\g<1>{waktu}', core)
    core = re.sub(r'<cp:revision>[^<]*</cp:revision>', '<cp:revision>1</cp:revision>', core)
    berkas['docProps/core.xml'] = core.encode()
    berkas.update(media)

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('[Content_Types].xml', berkas.pop('[Content_Types].xml'))
        for n, b in berkas.items():
            z.writestr(n, b)
    if keluar:
        tmp = Path(keluar).with_suffix('.tmp')
        tmp.write_bytes(buf.getvalue())
        tmp.replace(keluar)
    return buf.getvalue()
