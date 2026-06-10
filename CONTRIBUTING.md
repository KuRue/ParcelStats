# Contributing to ParcelStats

Thank you for your interest in contributing! Here's how to get started.

## Development Setup

1. Fork and clone the repository
2. Copy `.env.example` to `.env` and fill in your values
3. Start the development environment:
   ```bash
   docker compose up -d postgres redis
   cd frontend && npm install && npm run dev
   cd ml-service && pip install -r requirements.txt && uvicorn main:app --reload
   ```

## Code Style

- **Frontend**: TypeScript, ESLint (next config), Prettier
- **ML Service**: Python 3.12+, Ruff for linting, type hints preferred
- **Commits**: Conventional commits preferred (`feat:`, `fix:`, `chore:`)

## Adding a New Carrier

1. Create a new file in `ml-service/services/scraper/` named `{carrier_slug}.py`
2. Extend `BaseCarrierScraper` and implement the `track()` method
3. If using Playwright, add config to the `SCRAPER_CONFIGS` dict in `generic.py`
4. Register the scraper in `services/scraper/__init__.py`
5. Add the carrier to `database/seed/carriers.sql`
6. Test with a sample tracking number

## Pull Request Process

1. Ensure all tests pass
2. Update documentation if needed
3. Add your changes to the PR description
4. Link any related issues

## Reporting Issues

- Use the appropriate issue template (bug, feature, carrier request)
- Include steps to reproduce for bugs
- Include carrier name and tracking number format for carrier requests

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
