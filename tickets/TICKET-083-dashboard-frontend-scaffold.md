# TICKET-083 -- Dashboard React Frontend Scaffold

**Priority:** HIGH
**Effort:** 2 hours
**Status:** DONE
**Depends on:** None (can be built in parallel with backend)
**Files:**
- `dashboard/frontend/` (entire Vite + React + TypeScript project)

## Description

Create the React frontend scaffold:

1. `npm create vite@latest frontend -- --template react-ts`
2. Install dependencies: react-router-dom, @tanstack/react-query,
   @tanstack/react-table, lightweight-charts, recharts, react-markdown,
   remark-gfm, rehype-highlight, tailwindcss, lucide-react
3. Configure Tailwind with dark theme colors from SPEC
4. Configure Vite proxy: `/api` -> `http://localhost:8080`
5. Create Layout component with nav bar (5 pages)
6. Create React Router with routes for all 5 pages
7. Create API client module with fetch wrapper + react-query setup
8. Create WebSocket hook (`useWebSocket`)
9. Create polling hook (`usePolling`)
10. Create TypeScript interfaces matching Pydantic models

## Acceptance Criteria

- [ ] `npm run dev` starts Vite dev server
- [ ] Navigation between 5 pages works
- [ ] Dark theme applied globally
- [ ] API client can fetch from `/api/health`
- [ ] WebSocket hook connects to `/ws/live`
