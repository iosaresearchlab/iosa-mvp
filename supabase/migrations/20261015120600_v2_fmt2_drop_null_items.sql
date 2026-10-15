-- FMT-2 closed (15/10/2026): fmt2_null_items is dropped, as 02 section 4.10
-- says. It held the inventory items whose format was unknown when FMT-1
-- started (captured 04/10, migrations 20261004133725 and 20261004154702):
-- working data that told phase 2 which items to re-read. The recovery is
-- over; what it changed is kept in fmt2_history (old values, the rollback)
-- and fmt2_left (the 75 records left under the old rule).
--
-- Run by the owner in the SQL Editor of project jodgdhkfkgvbyirvfcds on
-- 2026-10-15 at about 12:06 UTC (owner's go-ahead the same day; the
-- migration tool refused the statement), so it is not listed in
-- supabase_migrations. 6,202 rows, 10,862,592 bytes; database
-- 252,300,435 -> 241,446,035 bytes.
--
-- Rollback: none for the content (a snapshot of 04/10 that the inventory no
-- longer holds); the table itself is recreated by the two migrations above.

drop table public.fmt2_null_items;
