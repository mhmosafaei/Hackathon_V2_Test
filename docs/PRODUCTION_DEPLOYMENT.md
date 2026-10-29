# PermitPulse deployment: Render + Vercel

**Status: configuration scaffold, NOT production-authorized.** Do not expose the API to untrusted users until authentication, per-user isolation and security review are complete.

## Render
Create a Render Blueprint from render.yaml on branch deploy/render-vercel-production. Use a paid plan with a persistent disk (the blueprint uses starter and 1 GB). Set PERMITPULSE_DEMO_USERNAME and a long random PERMITPULSE_DEMO_PASSWORD as Render secrets; the Blueprint enables PERMITPULSE_PRIVATE_DEMO=1. Set OPENAI_API_KEY, OPENAI_MODEL and PERMITPULSE_ALLOWED_ORIGIN in Render's secret environment settings; never commit credentials. Add any required Copernicus/ECMWF credentials per the operator guide. Verify disk mounting and cache symlink, then test /api/health.

Render disk storage is single-instance. The backend intentionally uses one worker because app.state is process-local. Restarts lose active in-memory state, although persisted analysis/reviews remain on disk. This is not safe for multiple concurrent independent users: global boot_id and shared active analysis state are not user-isolated.

## Vercel
Import the same repository, select branch deploy/render-vercel-production as the production branch (or merge the PR to the chosen production branch), set root directory frontend, framework Vite, build npm run build, output dist, install npm ci.

**Before deploying**, replace REPLACE_WITH_RENDER_HOST in frontend/vercel.json with the actual Render hostname. Vercel rewrites preserve the /api path and avoid browser CORS. Set PERMITPULSE_ALLOWED_ORIGIN on Render to the exact HTTPS Vercel production origin (e.g. https://your-project.vercel.app), without trailing slash. Verify request Origin and forwarded host handling against deployed proxies.

## Private demo access\n\nUse HTTPS only. The backend requires Basic authentication on all routes except /api/health when PERMITPULSE_PRIVATE_DEMO=1. Never share the demo password in GitHub or chat. This is shared-operator access, not user isolation. Browser prompts through the Vercel rewrite must be verified in a real deployment. A public Vercel shell may still render before its API requests receive a 401; use Vercel Deployment Protection too if the entire UI must be private. Rotate the password after the hackathon.\n\n## Security release gate
- Do not publish a fully functional public demo before implementing authentication, per-user authorization and isolation of analysis/review state and persisted evidence.
- The existing session boot ID is not an authentication mechanism. Anyone who can reach the backend could access shared state.
- Direct Render API URL must also be protected; an origin check is not authentication.
- Verify provider quotas, request duration limits, data retention and access to sensitive permit PDFs.
- Test upload, restore, human review, environmental fetch, decision windows and restart persistence with synthetic documents.
- Avoid setting a wildcard origin. Never commit secrets or real permit PDFs.

## Notes
Vite's local development proxy in vite.config.js remains unchanged. The production frontend uses the Vercel rewrite. This deployment uses the existing FastAPI factory, not the legacy Streamlit app.
