-- FIX-1c (20/10/2026): sitemap_creators() removed (owner, 20/10). It was
-- applied to production while measuring (migration 20261020183800) and never
-- used: same 7,203 handles as the sitemap's own read, not faster as anon.
-- Nothing calls it (frontend, backend, tests).
--
-- Rollback: re-apply 20261020183800_v2_fix1c_sitemap_creators.sql.

drop function if exists public.sitemap_creators(date, int);
