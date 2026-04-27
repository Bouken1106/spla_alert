# spla-alert webtest outputs

Downloaded Splatoon gameplay/HUD images used to validate the detector.

- `source_images/`: original images downloaded from the listed URLs
- `overlays/`: detector bounding boxes and alive/dead labels
- `results/`: detailed per-slot JSON metrics
- `manifest.json`: machine-readable source, expected, and actual counts

| status | fixture | expected | actual | source |
| --- | --- | --- | --- | --- |
| PASS | inkipedia_s3_replay | 4/4,4/4 | 4/4,4/4 | https://splatoonwiki.org/wiki/File:S3_Replay_screenshot_JP.jpg |
| PASS | reddit_s2_hud_dead_icon | 3/4,4/4 | 3/4,4/4 | https://www.reddit.com/r/splatoon/comments/s49930/what_do_the_squid_icons_at_the_top_mean/ |

