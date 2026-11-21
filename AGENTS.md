# Course contribution instructions

- Write reader-facing course content in simplified Chinese; use English for code, comments, and commits.
- Preserve the original planning kit under `ai-agent-engineering-book-kit/`.
- Never publish raw interviews, personal identifiers, credentials, or unverified company claims.
- Prefer an editable diagram, then a comparison table, then short explanatory prose.
- Every new chapter must state scope, prerequisites, learning outcomes, an exercise, acceptance criteria, and sources.
- Distinguish working slices from completed chapters. Do not mark a 24-chapter specification complete after delivering only an introductory slice.
- Use Python 3.11+ standard-library labs where practical. Label scripted models and synthetic data.
- Verify version-sensitive claims against primary sources. Record the supported claim and access date.
- Run `python3 scripts/check_book.py` and relevant lab tests before committing.
- Do not use sed. Do not use a browser for UI verification; leave visual acceptance to the user.
- Keep parallel work scoped to assigned files. Do not overwrite another contributor's work.
