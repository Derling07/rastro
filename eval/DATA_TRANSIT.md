# Transit clip storage (Round 3)

Root `DATA.md` says demo videos are **not** redistributed in Git (LILA paths are gitignored). Same policy for transit:

- Binaries live under `data/transit/` on the box (`*.ogv` / `*.webm` originals + `*.mp4` H.264 derivatives).
- Root `.gitignore` currently ignores only `data/lila/**/*.{mp4,MP4,avi,AVI}` — it does **not** list `data/transit/`. Do **not** `git add` the video blobs unless ORION explicitly wants them in-repo.
- Tracked beside the downloads: `data/transit/ATTRIBUTION.md` (licenses + curl URLs).
- Re-download:

```bash
mkdir -p data/transit && cd data/transit
curl -L -o chiang_mai_intersection.ogv \
  "https://upload.wikimedia.org/wikipedia/commons/2/21/A_intersection_with_traffic_in_Chiang_Mai%2C_Thailand.ogv"
curl -L -o wicker_park_intersection.webm \
  "https://upload.wikimedia.org/wikipedia/commons/0/0b/Wicker_Park_intersection_changes.webm"
ffmpeg -y -i chiang_mai_intersection.ogv -c:v libx264 -preset fast -crf 23 -vf scale=-2:720 -an chiang_mai_intersection.mp4
ffmpeg -y -i wicker_park_intersection.webm -c:v libx264 -preset fast -crf 23 -vf scale=-2:720 -an wicker_park_intersection.mp4
```

ORION note (Round 3): CC BY / BY-SA traffic clips under 500 MB OK; prefer smaller — both clips are ≪50 MB after convert.
