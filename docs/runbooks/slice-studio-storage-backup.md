# Slice Studio Storage Backup

Slice Studio local runtime data lives in:

```text
apps/slice-studio/storage/app.sqlite
apps/slice-studio/storage/projects/
```

This data is ignored by Git and must not be committed. Back it up before moving app paths, changing storage defaults, running destructive cleanup, or doing production migration work.

## Backup

From the repository root:

```bash
timestamp="$(date +%Y%m%d-%H%M%S)"
backup_dir="backups/slice-studio-storage-$timestamp"
mkdir -p "$backup_dir"
cp -a apps/slice-studio/storage/app.sqlite "$backup_dir/app.sqlite"
cp -a apps/slice-studio/storage/projects "$backup_dir/projects"
sqlite3 "$backup_dir/app.sqlite" \
  'select "projects", count(*) from projects union all select "pages", count(*) from pages union all select "slices", count(*) from slices;'
du -sh "$backup_dir"
```

`backups/` is ignored by Git.

## Restore

Stop Slice Studio first. Then restore:

```bash
cp -a backups/slice-studio-storage-YYYYMMDD-HHMMSS/app.sqlite apps/slice-studio/storage/app.sqlite
rm -rf apps/slice-studio/storage/projects
cp -a backups/slice-studio-storage-YYYYMMDD-HHMMSS/projects apps/slice-studio/storage/projects
```

Start Slice Studio and verify:

```text
/projects lists existing projects
existing project source images load
existing slices appear
assets.zip export succeeds
project.zip export succeeds
```

## Current Checkpoint

2026-06-13 prelaunch backup:

```text
backups/slice-studio-storage-20260613-023319
projects=17
pages=47
slices=643
size=223M
```
