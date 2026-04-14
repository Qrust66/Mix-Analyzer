# Ableton Live Set (.als) Management

This section allows version-controlling and programmatically modifying Ableton Live Set files.

## How it works

Ableton `.als` files are **gzip-compressed XML**. The `als_utils.py` tool (at the repo root) can:

- **Decompress** `.als` to readable XML for inspection and editing
- **Recompress** modified XML back to `.als` for Ableton
- **Inspect** project info (tempo, tracks, time signature, etc.)

## Directory structure

```
ableton/
  projects/           <- Place your .als files here
    MyProject.als     <- Your Ableton Live Set
    MyProject.als.xml <- Decompressed XML (auto-generated)
```

## Workflow

### 1. Add your .als file

Copy your `.als` file into `ableton/projects/`, then commit and push:

```bash
cp "/path/to/your/Project.als" ableton/projects/
git add ableton/projects/Project.als
git commit -m "Add Ableton project: Project"
git push
```

### 2. Inspect the project

```bash
python als_utils.py info ableton/projects/Project.als
```

### 3. Decompress for editing

```bash
python als_utils.py decompress ableton/projects/Project.als
# Creates: ableton/projects/Project.als.xml
```

### 4. Edit the XML

The decompressed XML can be edited manually or by Claude. Changes can include:
- Track names, colors, grouping
- Tempo, time signature
- Device/plugin parameters
- Clip properties, warping settings
- Send levels, routing
- Mixer settings (volume, pan)

### 5. Recompress and use in Ableton

```bash
python als_utils.py compress ableton/projects/Project.als.xml
# Overwrites: ableton/projects/Project.als
```

Open the resulting `.als` file in Ableton Live.

## What Claude can modify

Given an `.als` file in this repo, Claude can:

| Modification | Description |
|---|---|
| Track renaming | Change track names for clarity |
| Color coding | Assign colors to tracks/clips |
| Tempo changes | Adjust project BPM |
| Volume/Pan | Set mixer levels |
| Send levels | Adjust return send amounts |
| Track grouping | Organize tracks into groups |
| Device parameters | Tweak plugin/effect settings |
| Clip properties | Modify clip names, colors, warp settings |

## Important notes

- Always keep a backup of your original `.als` file before modifications
- Test modified `.als` files in Ableton to verify changes
- Some complex modifications (audio warp markers, automation curves) require careful XML editing
- `.asd` analysis files are gitignored (Ableton regenerates them)
- Sample files in `Samples/` folders are gitignored (too large for git)
