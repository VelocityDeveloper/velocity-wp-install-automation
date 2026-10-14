// Tag pembeda mesin di menu Server: server hosting (servers.json, tujuan installer, CSF)
// vs PC kantor (servers-monitor.json: PC Lokal = dashboard ini, PC Backup; firewalld/ufw).
export const JENIS_SERVER = {
  hosting: { label: 'Hosting', kelas: 'biru', ket: 'Server hosting klien (DirectAdmin)' },
  lokal: { label: 'PC Lokal', kelas: 'ungu', ket: 'PC kantor: dashboard, installer, server dev' },
  backup: { label: 'PC Backup', kelas: 'teal', ket: 'PC kantor: tujuan backup DirectAdmin' },
}
export const jenisServer = (j) => JENIS_SERVER[j] || JENIS_SERVER.hosting
export const pcKantor = (s) => s?.jenis === 'lokal' || s?.jenis === 'backup'
