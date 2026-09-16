# FloodSense Agent Instructions

These instructions apply to the entire repository.

Before changing any backend, database, GIS, Django Admin, Expert System, DSS,
migration, demonstration-data, or official-data import code, read and follow:

- `docs/TEAM_DATABASE_AND_GIT_WORKFLOW.md`
- `docs/COMPLETE_WINDOWS_SETUP_GUIDE.md` for environment setup
- the `README.md` inside the applicable `research_data/` directory for data work

Before changing the custom Admin web interface, mobile assessment flow,
scenario behavior, Expert System governance, parameter handling, notifications,
location behavior, or other thesis-facing functionality, also read and follow:

- `docs/TA_CONSULTATION_SYSTEM_DECISIONS.md`
- `docs/ADMIN_WEB_7_DAY_IMPLEMENTATION_PLAN.md` for Admin web work

The current decisions in those two files supersede conflicting descriptions in
older day guides, diagrams, mockups, and demonstration instructions. Historical
documents remain useful evidence, but they are not permission to reintroduce a
superseded feature. When the source transcript and the current team decision
differ, preserve that distinction and ask for clarification rather than claiming
that the thesis adviser approved the team decision.

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
9. FloodSense is currently scenario-based. Do not add background rainfall
   monitoring, timers, continuous polling, live alerts, or real-time forecasting
   unless the documented research scope is explicitly revised.
10. The inference method and raw expert rules are not ordinary administrator
    controls. Expose only authorized, validated, versioned parameters and
    explicitly approved content workflows in the custom Admin portal.
