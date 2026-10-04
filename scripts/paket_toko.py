"""Paket yang memakai VD Store.

Toko Online (Custom & biasa) sejak 2026-09-15; Paket Marketplace Biasa sejak 2026-10-04
(permintaan user, contoh ghaffara.com): VD Store + VD Marketplace + child theme
velocity-marketplace-child, isi beranda lewat scripts/marketplace-biasa. Marketplace hanya
untuk instalasi baru: situs marketplace yang sudah ter-deploy tetap seperti semula.
"""
import re


def norm_paket(paket):
    return re.sub(r'\s+', '', (paket or '').lower())


def marketplace_biasa(paket):
    return norm_paket(paket) == 'paketmarketplacebiasa'


def marketplace_baru(paket, domain):
    if not marketplace_biasa(paket):
        return False
    import cari_logo
    return not cari_logo.sudah_terpasang(domain)


def pakai_vd_store(paket, domain=''):
    return 'tokoonline' in norm_paket(paket) or marketplace_baru(paket, domain)
