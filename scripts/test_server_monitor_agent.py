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


class IdracTest(unittest.TestCase):
    def test_urai_sensor_daya_dan_psu(self):
        sdr = """Inlet Temp       | 04h | ok  |  7.1 | 34 degrees C
Exhaust Temp     | 01h | ok  |  7.1 | 49 degrees C
Temp             | 0Eh | ok  |  3.1 | 67 degrees C
Temp             | 0Fh | ok  |  3.2 | 68 degrees C
Current 1        | 6Ah | ok  | 10.1 | 1 Amps
Current 2        | 6Bh | ns  | 10.2 | No Reading
Voltage 1        | 6Ch | ok  | 10.1 | 228 Volts
Status           | 62h | ok  | 10.1 | Presence detected
Status           | 63h | ok  | 10.2 | Presence detected, Power Supply AC lost
Pwr Consumption  | 77h | ok  |  7.1 | 224 Watts"""
        ambang = """Sensor ID              : Inlet Temp (0x4)
 Upper Non-Critical    : 42.000
 Upper Critical        : 47.000
Sensor ID              : Exhaust Temp (0x1)
 Upper Non-Critical    : 70.000
 Upper Critical        : 75.000"""
        energi = """Statistic      : Cumulative Energy Consumption
Start Time     : Thu Jan  4 14:09:30 2024
Reading        : 3367.3 kWh

Statistic      : System Peak Power
Start Time     : Thu Jan  4 14:09:30 2024
Peak Time      : Mon Dec  9 19:06:16 2024
Peak Reading   : 368 W"""
        d = agent.urai_idrac(sdr, ambang, energi)
        self.assertEqual((d['inlet'], d['exhaust'], d['cpu'], d['watt']), (34, 49, [67, 68], 224))
        self.assertEqual((d['inlet_waspada'], d['inlet_kritis'], d['exhaust_kritis']), (42, 47, 75))
        self.assertEqual((d['kwh'], d['kwh_sejak'], d['puncak_watt']), (3367.3, 1704377370, 368))
        self.assertEqual([(p['nama'], p.get('volt'), p.get('amp'), p['masalah']) for p in d['psu']],
                         [('PS1', 228, 1, False), ('PS2', None, None, True)])

    def test_urai_kipas_sel_chassis(self):
        sdr = """Fan1A            | 30h | ok  |  7.1 | 5040 RPM
Fan2A            | 32h | cr  |  7.1 | 0 RPM
Fan Redundancy   | 75h | ok  |  7.1 | Fully Redundant
PS Redundancy    | 74h | ns  |  7.1 | No Reading"""
        sel_info = "Entries          : 575\nPercent Used     : 56%"
        sel = """ 12c | 12/09/2024 | 19:06:23 | Power Supply Status | Power Supply AC lost | Asserted
 12d | 12/03/2025 | 02:09:47 | Temperature Inlet Temp | Upper Non-critical going high | Asserted | Reading 42 > Threshold 42 degrees C"""
        chassis = "Power Restore Policy : previous\nChassis Intrusion    : inactive\nDrive Fault          : false\nCooling/Fan Fault    : true"
        d = agent.urai_idrac(sdr, sel_info=sel_info, sel=sel, chassis=chassis)
        self.assertEqual([k['ok'] for k in d['kipas']], [True, False])
        self.assertEqual(d['kipas_redundansi'], 'Fully Redundant')
        self.assertNotIn('psu_redundansi', d)
        self.assertEqual((d['sel']['entri'], d['sel']['persen']), (575, 56))
        self.assertEqual(d['sel']['terakhir'][0]['sensor'], 'Temperature Inlet Temp')  # terbaru dulu
        self.assertEqual(d['sel']['terakhir'][0]['t'], 1764727787)
        self.assertEqual(d['chassis'], {'restore': 'previous', 'intrusion': 'inactive', 'gangguan': ['Cooling/Fan Fault']})

    def test_tanpa_bmc_none(self):
        with patch.object(agent.os.path, 'exists', return_value=False):
            self.assertIsNone(agent.idrac())


if __name__ == '__main__':
    unittest.main()
