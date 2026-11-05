# Data for the Galvor tech intern assignment

The brand is **Little Joys**, an Indian kids' nutrition brand (milk mixes, gummies). You get 100 of its video ads and 20 Instagram creators it could work with next.

What is real and what is not:

- The ads, their videos, transcripts and copy are real public ads from the Meta Ad Library. Launch and stop dates are real.
- The creators, their posts, captions, likes, plays and transcripts are real public Instagram data.
- The labels (hook type, format, child on screen, and so on) were added by Galvor's AI system. They are mostly right but not always. Check any label you rely on.
- **The performance numbers in `ads.csv` (spend, impressions, purchases, revenue) are made up for this exercise.** They are not Little Joys' real results. Treat them as if they were the brand's own ad account export.

## Files

| File | Rows | What it holds |
| --- | --- | --- |
| `ads.csv` | 100 | One row per ad: dates, video link, transcript, labels, performance |
| `creators.csv` | 20 | One row per creator: profile, followers, a written read of their feed |
| `creator_posts.csv` | 392 | One row per recent post of those 20 creators: numbers, labels, and a transcript for about 6 posts each |
| `creator_audience.csv` | 3 | Audience age, gender and cities for the 3 creators we hold it for |

Videos: every ad's `video_url` is a direct MP4 link you can download. Creator posts link to Instagram (`post_url`).

## ads.csv

| Column | Meaning |
| --- | --- |
| `ad_id` | Our id for the ad |
| `meta_ad_library_id` | The ad's id in the Meta Ad Library |
| `video_url` | MP4 of the ad |
| `launch_date`, `stopped_date`, `days_live` | When it started, when it stopped (blank = still live on 26 Oct 2026), days it ran up to 26 Oct 2026 |
| `duration_s`, `language` | Length in seconds; main spoken language |
| `ad_copy` | The text posted with the ad |
| `transcript` | Everything said in the ad |
| `hook_line` | The opening line |
| `on_screen_text`, `claims_made` | Text shown on screen; product claims the ad makes |
| `hook_type`, `hook_driver`, `hook_delivered_by`, `hook_text_on_screen` | How the ad opens and what it plays on |
| `ad_format`, `story_structure`, `main_benefit`, `performance_style`, `humour` | What kind of ad it is and what it sells on |
| `creator_type`, `creator_gender`, `creator_age`, `people_on_screen` | Who is on screen |
| `child_on_screen`, `child_age`, `child_role`, `child_in_first_3s` | Whether a child appears and what they do (for example `reacts_to_taste`) |
| `brand_first_said`, `brand_said_aloud` | How soon the brand name is said |
| `product_form`, `product_shown_as`, `demo_shown`, `proof_used`, `persuasion` | How the product is shown and argued for |
| `production`, `audio`, `music`, `captions`, `language_mixing`, `first_frame`, `setting` | How it was made |
| `cta_type`, `offer` | The ask at the end |
| `narratives`, `ad_categories` | Broader themes, from a list made for kids' nutrition brands |
| `spend_inr` … `revenue_inr` | Made-up performance from launch to 26 Oct 2026: spend (₹), impressions, 3-second views, ThruPlays, link clicks, add to carts, purchases, revenue (₹) |

Lists inside a cell are separated by `; `.

## creators.csv

Profile fields (`handle`, `bio`, `followers`, `following`, `total_posts`, `verified`) plus our system's read of the feed: `persona`, `feed_story`, `voice`, `language_use`, `catchphrases`, `themes`, `format_habits`, `what_feels_native`, `what_would_feel_foreign`, `audience_read`.

## creator_posts.csv

Per post: `post_url`, `posted_on`, `type`, `duration_s`, `caption`, `plays`, `likes`, `comments`, `reshares`, then labels: `content_type`, `content_form`, `topic`, `hook_style`, `creator_on_camera`, `children_on_camera`, `child_ages`, `presenter_age`, `presenter_gender`, `language`, `setting`, `tone`, `product_shown`, `is_sponsored`, `brands_visible`, `production_quality_1to5`, `audience_signal`, `on_screen_text`, `what_stands_out`, and `transcript` where we have one. Some accounts hide like counts, which shows as 0 or a very low number.

## creator_audience.csv

Share of women and men, age split, top cities and countries, and brands the creator worked with in the past year. As of 29 Oct 2026. Only 3 of the 20 creators have this.
