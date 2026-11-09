#!/usr/bin/env python3
"""Perhitungan total disk fisik pada monitoring server."""
import unittest
from unittest.mock import patch

import server_monitor_agent as agent


class TotalDiskTest(unittest.TestCase):
    def sistem_dengan_lsblk(self, hasil):
        def jalan(cmd, batas=15):
            return hasil if cmd[0] == 'lsblk' else (0, '')

        with patch.object(agent, 'jalan', side_effect=jalan), patch.object(agent.time, 'sleep'):
            return agent.sistem()

    def test_menjumlahkan_disk_tanpa_loop(self):
        data = self.sistem_dengan_lsblk((0, 'disk 1000\ndisk 2000\nloop 500\n'))
        self.assertEqual(data['disk_fisik_total'], 3000)

    def test_gagal_atau_tidak_valid_tidak_menghasilkan_total(self):
        for hasil in [(-1, ''), (0, 'loop 500\n'), (0, 'disk 1000\ndisk -\n')]:
            with self.subTest(hasil=hasil):
                self.assertNotIn('disk_fisik_total', self.sistem_dengan_lsblk(hasil))

    def test_sisa_pool_tidak_menjumlahkan_dataset_anak(self):
        def jalan(cmd, batas=15):
            if cmd[0] == 'zpool':
                return 0, 'Backup\t3000\t2000\t1000\t67\tONLINE\n'
            if cmd[-1] == 'name,available':
                return 0, 'Backup\t800\nBackup/nextcloud\t200\n'
            return 0, ''

        with patch.object(agent, 'jalan', side_effect=jalan):
            pool = agent.penyimpanan()['pool'][0]
        self.assertEqual(pool['tersedia'], 800)
        self.assertEqual(pool['persen'], 67)

    def test_sisa_pool_tidak_dipalsukan_jika_zfs_gagal(self):
        def jalan(cmd, batas=15):
            if cmd[0] == 'zpool':
                return 0, 'Backup\t3000\t2000\t1000\t67\tONLINE\n'
            return -1, ''

        with patch.object(agent, 'jalan', side_effect=jalan):
            pool = agent.penyimpanan()['pool'][0]
        self.assertNotIn('tersedia', pool)


if __name__ == '__main__':
    unittest.main()
