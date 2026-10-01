/** Identitas aplikasi dari Pengaturan > Aplikasi (prop bersama `site`). */
export type Site = {
    name: string;
    description: string | null;
    logo_url: string;
    favicon_url: string;
    can_manage: boolean;
};
