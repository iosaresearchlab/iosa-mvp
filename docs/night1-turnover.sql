-- 24-hour turnover, measured on production: night 1 (2026-09-26) against
-- day 0 (2026-09-25). Run on 27/09/2026; the result is below the query.
with e as (
  select t.* from trend_snapshot t
  where day = '2026-09-26'
    and not exists (select 1 from trend_snapshot p
                    where p.day = '2026-09-25' and p.video_id = t.video_id))
select count(*)                                                   as entering_videos,
       count(distinct channel_id)                                 as entering_channels,
       count(*) filter (where format = 'LONG')                    as long_videos,
       count(distinct channel_id) filter (where format = 'LONG')  as long_channels,
       count(*) filter (where format = 'SHORT')                   as short_videos,
       count(distinct channel_id) filter (where format = 'SHORT') as short_channels,
       (select count(distinct channel_id) from trend_snapshot where day = '2026-09-26') as channels_26,
       (select count(*) from trend_snapshot a join trend_snapshot b
          on a.video_id = b.video_id and b.day = '2026-09-25'
        where a.day = '2026-09-26')                               as videos_in_both
from e;
-- entering_videos 6139 | entering_channels 5822 | long_videos 2015 | long_channels 1962
-- short_videos 4124 | short_channels 3882 | channels_26 21933 | videos_in_both 21544
-- (27,683 videos on 26/09; 27,593 on 25/09. 6,138 records were written: one
-- entry had no view count.)
