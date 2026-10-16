# RACAAL v2 implementation package

## Files
- `index.html` — dashboard and Bible module controls
- `control-center.css` — responsive, eye-friendly mobile styling
- `control-center.js` — dashboard API actions including Bible Send Now
- `main.py` — API changes, seven-day default trial, Bible Send Now endpoint
- `core_bot.py` — existing bot source included for the next integration pass
- `setup.html` — existing setup page
- `RACAAL_V2_FEATURE_SPEC.md` — Free/Premium rules and advanced protection backlog

## GitHub commit messages
Frontend:
`Build mobile-friendly RACAAL dashboard and Bible controls`

API:
`Add seven-day trial default and Bible send-now endpoint`

Bot (only after the bot changes are implemented and tested):
`Integrate RACAAL entitlements and recurring Bible automation`

## Upload guidance
1. Back up the deployed repositories and current Render services.
2. Frontend repository: upload `index.html`, `control-center.js`, and `control-center.css` together in the same deployed folder.
3. API repository/service: upload `main.py`. Keep the current requirements/dependency manifest and Render start command.
4. Bot repository/service: `core_bot.py` is included as the existing source; do not replace a live bot until recurring Bible scheduling, entitlement enforcement, and moderation changes are tested.
5. Do not commit bot tokens, Supabase service-role keys, AI API keys, or sync secrets.
6. Deploy the API before the frontend. Check `/health`, then open the private bot link and test in a test group.
7. Test Bible settings save/reload and `Send Daily Test Now`. The manual send-now endpoint posts the configured title/text; it does not yet generate quiz questions or implement recurring daily delivery.
8. Run the checklist in `RACAAL_V2_FEATURE_SPEC.md` before enabling features for customers.

## Important limitation
This is a staged implementation package, not a claim that all requested features are finished. Advanced protection, real recurring Bible daily tests/quiz content scheduling, payment renewal, and comprehensive server-side entitlement checks still need additional implementation and live Telegram verification.
