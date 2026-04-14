# Mathematics Department Schedules

* [Spring 2026 Schedule](https://ccsf-math.github.io/schedule/sp26.html)
* [Summer 2026 Schedule](https://ccsf-math.github.io/schedule/su26.html)
* [Fall 2026 Schedule](https://ccsf-math.github.io/schedule/fa26.html)

## How to update a schedule

1. Export the CSV from Courseleaf as usual.
2. Rename it to match the semester code — e.g. `fa26.csv`, `sp26.csv`, `su26.csv`.
3. Drag and drop it into this GitHub repository (or upload via the **Add file** button).
4. Commit directly to `main`.

That's it. GitHub Actions will automatically:
- Detect which CSV was uploaded
- Run `update_schedule.py` against the matching HTML file (e.g. `fa26.csv` → `fa26.html`)
- Stamp the **Updated** line in the HTML with the current date and time (UTC)
- Commit the updated HTML back to the repository

You can watch the progress under the **Actions** tab in the repository.

---

## File naming convention

| Semester    | CSV filename | HTML filename |
|-------------|--------------|---------------|
| Fall 2026   | `fa26.csv`   | `fa26.html`   |
| Spring 2026 | `sp26.csv`   | `sp26.html`   |
| Summer 2026 | `su26.csv`   | `su26.html`   |

The stem of the CSV must exactly match the stem of the HTML file.

---

## Repository structure

```
.
├── .github/
│   └── workflows/
│       └── update-schedule.yml   ← GitHub Actions workflow (do not delete)
├── update_schedule.py            ← Python script (do not delete)
├── fa26.csv / fa26.html
├── sp26.csv / sp26.html
└── su26.csv / su26.html
```

## Running locally (optional)

```bash
python3 update_schedule.py fa26.csv fa26.html
```

---

## Timestamp format

The **Updated** line in each HTML file is set to the UTC time of the GitHub Actions run:

```
Updated 4/13/2026, 02:45 PM UTC
```
