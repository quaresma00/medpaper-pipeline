---
description: Resume or start the medpaper research pipeline at the correct stage
---

Run `python tools/wf.py status` and follow the stage card it prints, exactly.

Then `python tools/wf.py check`, fix everything it reports, and close the stage with
`python tools/wf.py advance --note "..."`.

Do not skip stages, do not work from memory, and do not create files the stage does not
declare.
