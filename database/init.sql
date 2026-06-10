CREATE EXTENSION IF NOT EXISTS "postgis";
CREATE EXTENSION IF NOT EXISTS "timescaledb" CASCADE;

BEGIN;

CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    google_id TEXT UNIQUE NOT NULL,
    email TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    avatar_url TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE carriers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    slug TEXT UNIQUE NOT NULL,
    country TEXT,
    api_available BOOLEAN NOT NULL DEFAULT false,
    scrape_available BOOLEAN NOT NULL DEFAULT false,
    base_url TEXT,
    tracking_url_template TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE shipments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tracking_number TEXT NOT NULL,
    carrier_id UUID NOT NULL REFERENCES carriers(id),
    user_id UUID REFERENCES users(id),
    status TEXT NOT NULL DEFAULT 'pending',
    service_type TEXT,
    weight_kg DECIMAL(8,3),
    origin_lat DECIMAL(9,6),
    origin_lng DECIMAL(9,6),
    origin_name TEXT,
    dest_lat DECIMAL(9,6),
    dest_lng DECIMAL(9,6),
    dest_name TEXT,
    shipped_at TIMESTAMPTZ,
    delivered_at TIMESTAMPTZ,
    estimated_delivery TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(tracking_number, carrier_id)
);

CREATE TABLE shipment_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    shipment_id UUID NOT NULL REFERENCES shipments(id) ON DELETE CASCADE,
    status TEXT NOT NULL,
    location_lat DECIMAL(9,6),
    location_lng DECIMAL(9,6),
    location_name TEXT,
    description TEXT,
    raw_data JSONB,
    event_time TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE predictions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    shipment_id UUID NOT NULL REFERENCES shipments(id) ON DELETE CASCADE,
    predicted_delivery TIMESTAMPTZ NOT NULL,
    confidence_low TIMESTAMPTZ,
    confidence_high TIMESTAMPTZ,
    confidence_pct DECIMAL(5,2),
    model_version TEXT NOT NULL,
    features JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE carrier_routes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    carrier_id UUID NOT NULL REFERENCES carriers(id),
    origin_region TEXT NOT NULL,
    dest_region TEXT NOT NULL,
    service_type TEXT,
    avg_days DECIMAL(6,2),
    median_days DECIMAL(6,2),
    p10_days DECIMAL(6,2),
    p90_days DECIMAL(6,2),
    sample_count INTEGER NOT NULL DEFAULT 0,
    route_hops JSONB,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(carrier_id, origin_region, dest_region, service_type)
);

CREATE TABLE scrape_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    shipment_id UUID REFERENCES shipments(id) ON DELETE SET NULL,
    carrier_id UUID NOT NULL REFERENCES carriers(id),
    tracking_number TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    attempts INTEGER NOT NULL DEFAULT 0,
    last_error TEXT,
    next_attempt_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at TIMESTAMPTZ
);

CREATE TABLE model_versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    model_name TEXT NOT NULL,
    version TEXT NOT NULL,
    metrics JSONB,
    trained_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    is_active BOOLEAN NOT NULL DEFAULT false,
    UNIQUE(model_name, version)
);

CREATE INDEX idx_shipments_user_id ON shipments(user_id);
CREATE INDEX idx_shipments_tracking ON shipments(tracking_number, carrier_id);
CREATE INDEX idx_shipments_status ON shipments(status);
CREATE INDEX idx_shipments_carrier ON shipments(carrier_id);
CREATE INDEX idx_shipment_events_shipment ON shipment_events(shipment_id, event_time DESC);
CREATE INDEX idx_shipment_events_time ON shipment_events(event_time DESC);
CREATE INDEX idx_predictions_shipment ON predictions(shipment_id, created_at DESC);
CREATE INDEX idx_scrape_jobs_status ON scrape_jobs(status, next_attempt_at);
CREATE INDEX idx_carrier_routes_lookup ON carrier_routes(carrier_id, origin_region, dest_region);

SELECT create_hypertable('shipment_events', 'event_time', if_not_exists => true);
SELECT create_hypertable('predictions', 'created_at', if_not_exists => true);

CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_users_updated BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER trigger_shipments_updated BEFORE UPDATE ON shipments
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

COMMIT;
