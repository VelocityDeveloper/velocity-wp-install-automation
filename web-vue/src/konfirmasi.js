// Konfirmasi bergaya dashboard pengganti window.confirm(): `await konfirmasi({...})` → true/false.
// Ditampilkan oleh <KonfirmasiHost> di App.vue.
import { reactive } from 'vue'

export const keadaanKonfirmasi = reactive({ buka: false, judul: '', teks: '', tombol: 'Ya', kelas: '', selesai: null })

export function konfirmasi({ judul = 'Yakin?', teks = '', tombol = 'Ya, lanjutkan', kelas = '' } = {}) {
  return new Promise((selesai) => Object.assign(keadaanKonfirmasi, { buka: true, judul, teks, tombol, kelas, selesai }))
}
