# ParcelStats

AI-powered community-driven parcel tracking. Predict delivery dates with confidence intervals using machine learning and collective shipment data.

> **More people track = more data = better predictions for everyone.**

## Features

- **25+ International Carriers** — USPS, UPS, FedEx, DHL, Royal Mail, Canada Post, and more
- **AI ETA Predictions** — XGBoost-powered delivery predictions with confidence intervals
- **Route Analysis** — Historical route patterns and carrier performance stats
- **Cyber-themed UI** — Dark mode, neon accents, maps, and real-time updates
- **Google OAuth** — Secure authentication, no passwords
- **Community Intelligence** — Every tracked shipment improves the model
- **Self-hosted** — Full Docker stack, deploy anywhere

## Architecture

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   Traefik    │────▶│   Next.js    │────▶│ Python ML    │
│  (Proxy/SSL) │     │  (Frontend + │     │  (Predictions│
│              │     │   Node API)  │     │   + Scraping)│
└──────────────┘     └──────┬───────┘     └──────┬───────┘
                            │                     │
                     ┌──────▼─────────────────────▼──────┐
                     │     PostgreSQL + TimescaleDB       │
                     │     (Shipments, Predictions,       │
                     │      Routes, Events)               │
                     └────────────────────────────────────┘
                                         │
                                  ┌──────▼───────┐
                                  │    Redis      │
                                  │ (Cache/Queue) │
                                  └──────────────┘
```

## Quick Start

### Prerequisites

- Docker + Docker Compose
- Google OAuth credentials ([setup guide](#google-oauth-setup))

### 1. Clone and Configure

```bash
git clone https://github.com/YOUR_USERNAME/ParcelStats.git
cd ParcelStats
cp .env.example .env
```

### 2. Edit `.env`

```bash
DOMAIN=localhost
DB_PASSWORD=your_secure_password
NEXTAUTH_SECRET=openssl rand -base64 32
NEXTAUTH_URL=https://your-domain.com
GOOGLE_CLIENT_ID=your_google_client_id
GOOGLE_CLIENT_SECRET=your_google_client_secret

# Optional carrier API credentials. Required for reliable USPS, UPS, and FedEx tracking.
USPS_WEB_TOOLS_USER_ID=your_usps_web_tools_user_id
UPS_CLIENT_ID=your_ups_client_id
UPS_CLIENT_SECRET=your_ups_client_secret
FEDEX_CLIENT_ID=your_fedex_client_id
FEDEX_CLIENT_SECRET=your_fedex_client_secret
```

### 3. Launch

```bash
docker compose up -d
```

Visit `https://localhost` (or your domain).

### 4. Seed Carriers (first run)

```bash
docker exec -i parcelstats-postgres psql -U parcelstats -d parcelstats < database/seed/carriers.sql
```

## Google OAuth Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project
3. Enable "Google+ API"
4. Go to **Credentials** → **Create Credentials** → **OAuth Client ID**
5. Application type: **Web application**
6. Add authorized redirect URI: `https://your-domain.com/api/auth/callback/google`
7. Copy the Client ID and Client Secret to your `.env`

## Deployment (Unraid)

ParcelStats is designed to run as a Docker stack on Unraid:

1. Install the **Compose Manager** plugin on Unraid
2. Upload the project to your preferred location (e.g., `/mnt/user/appdata/parcelstats/`)
3. Copy and edit `.env` as described above
4. In the Unraid UI, go to the Compose tab and deploy

All data persists in Docker volumes. Back up the `postgres-data` volume regularly.

## Carrier Support

| Carrier | Method | Countries |
|---------|--------|-----------|
| USPS | Web Tools API | US |
| UPS | OAuth Track API | US |
| FedEx | OAuth Track API | US |
| DHL Express | API + Scrape | Global |
| Royal Mail | Playwright | UK |
| Canada Post | Playwright | CA |
| Australia Post | Playwright | AU |
| Deutsche Post | Playwright | DE |
| DHL Parcel DE | Playwright | DE |
| GLS | Playwright | EU |
| Hermes | Playwright | DE |
| China Post | Playwright | CN |
| Yanwen | Playwright | CN |
| Japan Post | Playwright | JP |
| India Post | Playwright | IN |
| Correos | Playwright | ES |
| Poste Italiane | Playwright | IT |
| La Poste | Playwright | FR |
| PostNord | Playwright | SE/DK/NO/FI |
| Swiss Post | Playwright | CH |
| An Post | Playwright | IE |
| NZ Post | Playwright | NZ |
| Singapore Post | Playwright | SG |
| Pos Malaysia | Playwright | MY |
| Thai Post | Playwright | TH |

**Adding a new carrier:** Open a [Carrier Request](../../issues/new?template=carrier_request.md) issue or submit a PR with a new scraper in `ml-service/services/scraper/`.

**Carrier API notes:** USPS, UPS, and FedEx block or redirect unauthenticated server-side tracking requests in many environments. Set `USPS_WEB_TOOLS_USER_ID`, `UPS_CLIENT_ID` + `UPS_CLIENT_SECRET`, and `FEDEX_CLIENT_ID` + `FEDEX_CLIENT_SECRET` before starting the stack. Without those values, matching shipments are marked `carrier_setup_required` instead of retrying into `tracking_exception`.

UPS defaults to the production API host `https://onlinetools.ups.com`. Set `UPS_BASE_URL=https://wwwcie.ups.com` for the UPS customer integration environment. FedEx defaults to `https://apis.fedex.com`; set `FEDEX_BASE_URL=https://apis-sandbox.fedex.com` for sandbox credentials.

## ML Prediction Model

### How it Works

1. **Data Collection** — Every tracked shipment's events, origin, destination, carrier, and timing are stored
2. **Feature Engineering** — Carrier, regions, service type, weight, seasonal patterns, day of week
3. **Training** — Three XGBoost models predict:
   - **Median ETA** — Most likely delivery date
   - **P10 bound** — 10th percentile (optimistic)
   - **P90 bound** — 90th percentile (conservative)
4. **Confidence Score** — Calculated from the spread between P10 and P90
5. **Retraining** — Automatic weekly retraining as data grows

When there is not enough completed shipment history to train the XGBoost model, ParcelStats stores fallback predictions from carrier-provided ETAs, route statistics, or conservative carrier baselines. These predictions are replaced by stronger model predictions once enough data exists.

### Improving Predictions

- Track more packages → more training data
- Different carriers and routes → better generalization
- Over time, confidence intervals narrow as the model learns patterns

## Project Structure

```
ParcelStats/
├── docker-compose.yml          # Full Docker stack
├── frontend/                   # Next.js app
│   ├── src/
│   │   ├── app/                # Pages + API routes
│   │   ├── components/         # React components
│   │   └── lib/                # Auth, DB, utilities
│   ├── drizzle.config.ts       # ORM config
│   └── Dockerfile
├── ml-service/                 # Python FastAPI
│   ├── routers/                # API endpoints
│   ├── services/
│   │   ├── predictor.py        # ML inference
│   │   ├── trainer.py          # Model training
│   │   └── scraper/            # Carrier scrapers
│   ├── database/               # SQLAlchemy models
│   └── Dockerfile
├── database/
│   ├── init.sql                # Schema
│   └── seed/                   # Carrier data
└── traefik/                    # Reverse proxy config
```

## Tech Stack

| Component | Technology |
|-----------|------------|
| Frontend | Next.js 14, React, TailwindCSS |
| Backend API | Next.js API Routes, Drizzle ORM |
| ML Service | Python, FastAPI, XGBoost, scikit-learn |
| Database | PostgreSQL + TimescaleDB |
| Scraping | Playwright, httpx, BeautifulSoup |
| Auth | NextAuth.js v5 (Google OAuth) |
| Maps | Leaflet + OpenStreetMap |
| Cache | Redis |
| Proxy | Traefik |
| Deployment | Docker Compose |

## Development

### Frontend

```bash
cd frontend
npm install
npm run dev
```

### ML Service

```bash
cd ml-service
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt
playwright install chromium
uvicorn main:app --reload --port 8000
```

### Database Migrations

```bash
cd frontend
npm run db:generate    # Generate migration from schema changes
npm run db:migrate     # Apply migrations
```

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

See [CONTRIBUTING.md](CONTRIBUTING.md) for details.

## License

MIT License — see [LICENSE](LICENSE) for details.

## Roadmap

- [ ] WebSocket real-time tracking updates
- [ ] Email/push notifications
- [ ] Mobile app (React Native)
- [ ] Public API for third-party integrations
- [ ] Route map visualization with animated paths
- [ ] Carrier reliability scores
- [ ] Neural network models for complex routes
- [ ] Multi-language support
- [ ] Dark/light theme toggle
- [ ] Package photo OCR for auto-tracking-number detection
