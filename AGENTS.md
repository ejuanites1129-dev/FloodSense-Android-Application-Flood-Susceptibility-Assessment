# FloodSense Agent Instructions

These instructions apply to the entire repository.

Before changing any backend, database, GIS, Django Admin, Expert System, DSS,
migration, demonstration-data, or official-data import code, read and follow:

- `docs/TEAM_DATABASE_AND_GIT_WORKFLOW.md`
- `docs/COMPLETE_WINDOWS_SETUP_GUIDE.md` for environment setup
- the `README.md` inside the applicable `research_data/` directory for data work

Non-negotiable rules:

1. Inspect `git status` first and preserve unrelated user changes.
2. Django models and committed migrations define shared database structure;
   local PostgreSQL rows and local superusers are not synchronized by Git.
3. Include a reviewed migration and tests with every intentional model change
   that requires one. Do not delete or rewrite shared migration history merely
   to repair one local database.
4. Never commit `.env`, credentials, local database dumps, personally
   identifiable information, or restricted agency/research data.
5. Do not claim that `seed_demo` or another import command exists without
   verifying it in the checked-out code.
6. Keep fictional/provisional records visibly labeled and separate from approved
   data. Never present invented classifications as official Bacoor information.
7. Before completion, run relevant checks/tests and state what teammates must
   run after pulling (dependencies, migrations, seeds/imports).
8. Run `git pull`, `git push`, migrations against a shared/deployed database, or
   official-data imports only when explicitly requested for that target.
