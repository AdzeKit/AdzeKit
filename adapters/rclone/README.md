# AdzeKit Rclone Adapter

Cloud sync for the workbench (`stock/` + `drafts/`). The backbone itself
syncs via git; rclone covers the workbench, which is git-ignored because
it's large and ephemeral. Together they make the shed portable across
machines:

```
backbone   ← git pull / git push       (loops/, projects/, knowledge/, daily/, reviews/)
workbench  ← rclone pull / rclone push (stock/, drafts/)
```

## Install

```bash
adzekit adapter install rclone --remote gdrive
# or with a specific subfolder
adzekit adapter install rclone --remote gdrive --folder adzekit-prod
```

This writes the `rclone_remote` field in your shed's `.adzekit` marker.
Install does NOT push anything; it only configures.

You must have:
- `rclone` on PATH (`brew install rclone` on macOS)
- A configured rclone remote (`rclone config` to set up `gdrive`, `s3`,
  etc.)

## Sync

```bash
adzekit adapter sync rclone --direction pull     # download
adzekit adapter sync rclone --direction push     # upload
adzekit adapter sync rclone                      # both
# or use the legacy top-level CLI:
adzekit sync pull
adzekit sync push
```

Pull is the canonical operation at session start — when you switch
machines, `git pull` brings the backbone and `adzekit adapter sync rclone
--direction pull` brings the workbench.

Push runs at session end — `daily-close` calls `push_workbench()` under
the hood when an rclone remote is configured (see `modules/daily.py`).

## Status

```bash
adzekit adapter status rclone
```

Reports the configured remote, whether the rclone binary is on PATH, and
the resolved stock/drafts remote paths.

## Uninstall

```bash
adzekit adapter uninstall rclone
```

Clears `rclone_remote` from `.adzekit`. Cloud content is NOT deleted —
the local rclone configuration still points there. Use `rclone purge`
manually if you want to wipe the cloud copy.

## Why this is an adapter

The same shape as `claude-code` and `hermes` — install / uninstall /
status / sync verbs over a host-system integration. AdzeKit core has rclone
helpers in `Settings` (`sync_workbench`, `push_workbench`, etc.) and the
adapter is a thin shim over them. The point of having it as an adapter is
discoverability: `adzekit adapter` is the single entry point for all
host-system integrations.

## Multi-machine flow

```
laptop:  edit notes, run skills → drafts pile up
         daily-close pushes drafts/ + stock/ to rclone

desktop: git pull (backbone)
         adzekit adapter sync rclone --direction pull  (workbench)
         drafts are now visible in INBOX
         adzekit drafts list
         adzekit drafts accept N   (promotes locally)
         git push (when satisfied with the day's promotions)
```

Multi-machine same-day writes will conflict in git when both machines
touch the daily note. The `-HHMM-host` suffix in draft filenames keeps
the workbench layer collision-free; only the daily note merges by hand.
