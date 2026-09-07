# GulzarSoft Frontend (Next.js)

## Run Locally

Node requirement: use Node LTS (18 or 20). Node 24 can break Next.js SWC native binaries on Windows.

1. Install dependencies:

   npm install

2. Configure environment:

   Copy `.env.local.example` to `.env.local` and update values if needed.

3. Start development server:

   npm run dev

The app runs at `http://localhost:3000` and calls backend route `POST /api/v1/chat`.

## Backend Requirement

Make sure your FastAPI backend is running at `http://localhost:8000` or set `NEXT_PUBLIC_API_BASE_URL` accordingly.
