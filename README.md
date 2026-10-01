# Deep Dive — Hub Map

A Roblox hub map for the game *Deep Dive*. It is built procedurally in Blender with Python and exported to FBX for Roblox Studio. The scene has 816 objects, 294 unique meshes and about 58k authored triangles. See [MANIFEST.md](MANIFEST.md) for the full breakdown.

- `src/`: build scripts, one per phase (`p1_greybox.py` … `p8_materials.py`), run by `build_all.py`
- `out/`: exported FBX files and NPC anchor data for Studio
- `renders/`: progress renders from every phase, plus the final `.blend` scene
- `refs/`: the reference blueprint

## Work log

This repository contains the full, unedited commit history. Each commit's timestamp records when that piece of work was saved. Run `git log --reverse` to see it, or check the commit list on GitHub.

| Date | Commits | First → last commit | Work |
|---|---|---|---|
| 2026-09-08 | 6 | 22:35 → 23:46 | Brief, scaffold, Phase 1 greybox, Phase 2 terrain, Phase 3 shop and spire |
| 2026-09-09 | 11 | 02:14 → 23:50 | Phase 4 plaza, Phase 5 plots, palette, Phase 6 harbour, Phase 4b Merchant Row, Phase 7a–7c prop kit and scatter |
| 2026-09-10 | 3 | 01:17 → 03:17 | Plaza fill, vignette placement, Phase 8 materials and FBX export |
| 2026-09-14 | 1 | 21:47 | Polish pass. The final renders and `.blend` were saved until 22:24 |

Commit times show when work was *saved*. Time spent before a session's first commit isn't captured, so these figures are a lower bound on hours worked.

## License

Copyright © 2026 David Bianchi. All rights reserved. See [LICENSE](LICENSE).
