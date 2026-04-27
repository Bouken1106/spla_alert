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
| PASS | inkipedia_s2_battle_ui_one_dead | 3/4,4/4 | 3/4,4/4 | https://splatoonwiki.org/wiki/File:S2_new_battle_UI_promo_EN.jpg |
| PASS | inkipedia_s2_spectator_view_two_dead | 3/4,3/4 | 3/4,3/4 | https://splatoonwiki.org/wiki/File:S2_Spectator_View_promo_1.jpg |
| PASS | inkipedia_s2_spectator_view_action_two_dead | 3/4,3/4 | 3/4,3/4 | https://splatoonwiki.org/wiki/File:S2_Spectator_View_promo_3.jpg |
| PASS | inkipedia_s2_spectator_view_all_alive | 4/4,4/4 | 4/4,4/4 | https://splatoonwiki.org/wiki/File:S2_Spectator_View_promo_4.jpg |
| PASS | inkipedia_s2_spectator_view_close_all_alive | 4/4,4/4 | 4/4,4/4 | https://splatoonwiki.org/wiki/File:S2_Spectator_View_promo_5.jpg |
| PASS | inkipedia_s3_replay_en | 4/4,4/4 | 4/4,4/4 | https://splatoonwiki.org/wiki/File:S3_Replay_EN.jpg |
| PASS | inkipedia_s3_replay_hidden_interface | 3/4,4/4 | 3/4,4/4 | https://splatoonwiki.org/wiki/File:S3_Replay_hidden_interface_EN.jpg |
| PASS | inkipedia_s3_replay_top_view | 4/4,4/4 | 4/4,4/4 | https://splatoonwiki.org/wiki/File:S3_Replay_screenshot_top_view_JP.jpg |
| PASS | inkipedia_s3_rainmaker_promotional | 3/4,3/4 | 3/4,3/4 | https://splatoonwiki.org/wiki/File:S3_Rainmaker_promotional_JP.jpg |
| PASS | inkipedia_s3_tower_objective_camera | 3/4,3/4 | 3/4,3/4 | https://splatoonwiki.org/wiki/File:S3_Towering_Tower_Control_Objective_Camera.png |
| PASS | inkipedia_s3_tower_control_tower | 4/4,4/4 | 4/4,4/4 | https://splatoonwiki.org/wiki/File:S3_Towering_Tower_Control_Tower.png |
| PASS | inkipedia_s2_spectator_map_view_no_top_hud | 0/4,0/4 | 0/4,0/4 | https://splatoonwiki.org/wiki/File:S2_Spectator_View_promo_2.jpg |
| PASS | inkipedia_s3_no_hud_squid_roll | 0/4,0/4 | 0/4,0/4 | https://splatoonwiki.org/wiki/File:S3_first_twitter_preview_-_squid_roll.jpg |
| PASS | inkipedia_s3_no_hud_shop | 0/4,0/4 | 0/4,0/4 | https://splatoonwiki.org/wiki/File:S3_Expansion_Pass_Jelly_Fresh_interior_EN.jpg |
| PASS | inkipedia_s3_no_hud_banners | 0/4,0/4 | 0/4,0/4 | https://splatoonwiki.org/wiki/File:S3_Banners_screenshot_EN.jpg |
| PASS | inkipedia_s3_no_hud_crab_n_go | 0/4,0/4 | 0/4,0/4 | https://splatoonwiki.org/wiki/File:S3_Crab-N-Go_promo.jpg |
| PASS | inkipedia_s3_no_hud_drop_into_battle | 0/4,0/4 | 0/4,0/4 | https://splatoonwiki.org/wiki/File:S3_drop_into_battle.jpg |
| PASS | inkipedia_s3_no_hud_splatsville_pig | 0/4,0/4 | 0/4,0/4 | https://splatoonwiki.org/wiki/File:Splatsville_pig.png |
| PASS | inkipedia_s3_no_hud_x100_battle_chance | 0/4,0/4 | 0/4,0/4 | https://splatoonwiki.org/wiki/File:Increased_x100_Battle_Chance_In_Chaos_vs_Order.jpg |
| PASS | inkipedia_s2_no_hud_turf_war_promo | 0/4,0/4 | 0/4,0/4 | https://splatoonwiki.org/wiki/File:S2_Turf_War_promo_1.jpg |
| PASS | inkipedia_s3_no_hud_tricolor_map | 0/4,0/4 | 0/4,0/4 | https://splatoonwiki.org/wiki/File:S3_Tricolor_Bluefin_Depot_JP.png |
| PASS | inkipedia_s1_no_hud_turf_war_promo_1 | 0/4,0/4 | 0/4,0/4 | https://splatoonwiki.org/wiki/File:S_Turf_War_promo_1.jpg |
| PASS | inkipedia_s1_no_hud_turf_war_promo_3 | 0/4,0/4 | 0/4,0/4 | https://splatoonwiki.org/wiki/File:S_Turf_War_promo_3.jpg |
| PASS | inkipedia_s1_no_hud_turf_war_promo_5 | 0/4,0/4 | 0/4,0/4 | https://splatoonwiki.org/wiki/File:S_Turf_War_promo_5.jpg |
| PASS | inkipedia_s2_no_hud_splashdown_promo_1 | 0/4,0/4 | 0/4,0/4 | https://splatoonwiki.org/wiki/File:S2_Splashdown_promo_1.jpg |
| PASS | inkipedia_s2_no_hud_splashdown_promo_2 | 0/4,0/4 | 0/4,0/4 | https://splatoonwiki.org/wiki/File:S2_Splashdown_promo_2.jpg |
| PASS | inkipedia_s2_no_hud_ultra_stamp_promo | 0/4,0/4 | 0/4,0/4 | https://splatoonwiki.org/wiki/File:S2_Ultra_Stamp_promo_1.jpg |

