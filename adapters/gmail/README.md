# Gmail adapter

Preflight + cached config for the `inbox-triage` skill family. The skill
does the actual email work; this adapter just validates that everything
is wired up.

## Install

```bash
gcloud auth application-default login          # one-time setup
adzekit adapter install gmail
```

The install:
- Runs `gcloud auth application-default print-access-token` to confirm
  auth works.
- Fetches the Gmail label list.
- Warns if expected labels (`AdzeKit/ActionRequired`, `AdzeKit/Urgent`)
  are missing — create them via Gmail's UI or
  `POST https://gmail.googleapis.com/gmail/v1/users/me/labels`.
- Caches the label-name → ID map at
  `{shed}/drafts/.adapters/gmail-labels.json` so skills don't have to
  refetch on every run.

## Status

```bash
adzekit adapter status gmail
```

Reports:
- whether `gcloud` is on PATH
- whether the token works
- which expected labels are missing
- the cached label IDs

## Uninstall

```bash
adzekit adapter uninstall gmail
```

Removes the cached label map. Does NOT revoke gcloud auth — run
`gcloud auth application-default revoke` separately if you want that.

## Why an adapter at all?

The inbox-triage skill could (and previously did) call gcloud + Gmail API
directly. The adapter pattern earns its keep here because:

1. **One auth check, many skills.** Any future skill that needs Gmail
   reads the same cached config.
2. **Labels evolve.** When you add a new label, re-run `install` to
   refresh the cache without touching skill code.
3. **Failure mode visibility.** `status` tells you in one line whether
   inbox-triage *could* run — the user doesn't discover the failure mid-
   triage run.
