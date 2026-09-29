# INC-1 (28/09/2026 reading). Run: python tests/repro_entries_timeout.py (needs pgserver).
# Reproduce the 28/09 timeout on a local PostgreSQL: stale statistics after a
# bulk insert of the day's snapshot, with and without an index on
# posts.external_post_id. Production sizes: 8,088 posts, 4 x ~27.5k rows.
import os, time, random, string, pgserver, psycopg
srv = pgserver.get_server(os.path.expanduser('~/pgdata-repro'), cleanup_mode='stop')
c = psycopg.connect(srv.get_uri(), autocommit=True)
cur = c.cursor()
cur.execute("""
drop table if exists trend_snapshot, posts, ingest_run cascade;
create table ingest_run (day date unique, outcome text);
create table posts (id serial primary key, external_post_id varchar, pad text) with (autovacuum_enabled = false);
create table trend_snapshot (day date, video_id text, channel_id text, pad text, primary key (day, video_id)) with (autovacuum_enabled = false);
create index trend_snapshot_day_idx on trend_snapshot (day);
create or replace function entries_of_day(d date) returns table(video_id text, gap_days int, entry_certain boolean)
language sql stable as $f$
  with previous as (select max(r.day) as pd from ingest_run r where r.day < d and r.outcome = 'ok')
  select s.video_id, case when previous.pd = d - 1 then 0 else d - previous.pd end, previous.pd = d - 1
  from trend_snapshot s, previous
  where s.day = d and previous.pd is not null
    and not exists (select 1 from trend_snapshot p where p.day = previous.pd and p.video_id = s.video_id)
    and not exists (select 1 from posts po where po.external_post_id = s.video_id);
$f$;
""")
rnd = random.Random(1)
ids = [''.join(rnd.choices(string.ascii_letters + string.digits, k=11)) for _ in range(60000)]
days = ['2026-09-25', '2026-09-26', '2026-09-27']
for i, d in enumerate(days):
    part = ids[i*8000: i*8000 + 27500]
    with cur.copy("copy trend_snapshot (day, video_id, channel_id, pad) from stdin") as cp:
        for v in part: cp.write_row((d, v, 'UC' + v, 'x' * 150))
    cur.execute("insert into ingest_run values (%s, 'ok')", (d,))
with cur.copy("copy posts (external_post_id, pad) from stdin") as cp:
    for v in ids[20000:28088]: cp.write_row((v, 'y' * 1500))
cur.execute("analyze")
# the new day, written after the last analyze: statistics say it has no rows
with cur.copy("copy trend_snapshot (day, video_id, channel_id, pad) from stdin") as cp:
    for v in ids[24000:51455]: cp.write_row(('2026-09-28', v, 'UC' + v, 'x' * 150))
def timed(label):
    cur.execute("set statement_timeout = '8s'")
    t = time.time()
    try:
        cur.execute("select count(*) from (select * from entries_of_day('2026-09-28') order by video_id offset 0 limit 1000) x")
        print(label, 'rows', cur.fetchone()[0], f'{time.time()-t:.2f}s')
    except psycopg.errors.QueryCanceled:
        print(label, 'TIMEOUT after', f'{time.time()-t:.2f}s')
    cur.execute("reset statement_timeout")
timed('stale stats, no index    :')
cur.execute("create index posts_external_post_id_idx on posts (external_post_id)")
timed('stale stats, with index  :')
cur.execute("drop index posts_external_post_id_idx")
cur.execute("analyze trend_snapshot")
timed('fresh stats, no index    :')
cur.execute("create index posts_external_post_id_idx on posts (external_post_id)")
timed('fresh stats, with index  :')
