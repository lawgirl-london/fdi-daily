# FDI Daily

A private daily podcast on FDI screening regimes. Every weekday morning a GitHub Action:

1. runs Claude Code headless (on a Claude subscription, no API key) to research the news
   since the last episode and write a ≤10-minute script that doesn't repeat earlier episodes,
2. reads it aloud with Microsoft Edge neural TTS (free),
3. stores the MP3 as a GitHub Release asset and publishes `feed.xml` on GitHub Pages,
4. so the new episode appears in Apple Podcasts.

## Files

| File | Purpose |
|---|---|
| `topics.md` | Editorial brief: regimes, priorities, sources. **Edit this to steer content.** |
| `config.json` | Voice, speed, word cap, retention, pronunciation fixes |
| `prompts/episode.md` | Instructions Claude follows each day |
| `data/coverage.json` | Every story already covered, used to avoid repeats (kept 120 days) |
| `data/deals.json` | Deal tracker: blocked / conditioned / withdrawn / pending deals (kept permanently, shown at `/deals.html`) |
| `data/episodes.json` | Episodes in the feed (kept 30 days; older MP3 releases are deleted) |
| `scripts/tts.py`, `scripts/publish.py` | Audio generation; feed and web page rendering |
| `.github/workflows/daily.yml` | The schedule (Mon–Fri ~06:15 London) |

## One-time setup

1. Create a **public** repo `fdi-daily` on the listener's GitHub account and push this folder.
2. Settings → Pages → Source: **GitHub Actions**.
3. Settings → Environments → `github-pages` → Deployment branches: allow `main`.
4. On a machine with Claude Code: `claude setup-token`, then add the token as repo secret
   `CLAUDE_CODE_OAUTH_TOKEN` (`gh secret set CLAUDE_CODE_OAUTH_TOKEN`).
5. Actions → Daily episode → **Run workflow** for the first episode.
6. On the iPhone: Podcasts → Library → ⋯ → Follow a Show by URL →
   `https://<user>.github.io/fdi-daily/feed.xml`

## Tweaks

- **Different voice:** set `voice` in `config.json` (e.g. `en-GB-LibbyNeural`, `en-GB-RyanNeural`;
  full list: `edge-tts --list-voices`). Speed: `rate`, e.g. `"+10%"`.
- **Mispronounced acronym:** add it to `pronunciations` in `config.json`.
- **Time of day:** `cron` in `daily.yml` (UTC).
