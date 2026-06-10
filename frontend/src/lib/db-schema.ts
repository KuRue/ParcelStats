import { pgTable, uuid, text, timestamp, boolean, decimal, jsonb, integer, uniqueIndex } from "drizzle-orm/pg-core";

export const users = pgTable("users", {
  id: uuid("id").primaryKey().defaultRandom(),
  name: text("name").notNull(),
  email: text("email").unique().notNull(),
  emailVerified: timestamp("email_verified", { withTimezone: true }),
  image: text("image"),
  googleId: text("google_id").unique(),
  passwordHash: text("password_hash"),
  createdAt: timestamp("created_at", { withTimezone: true }).notNull().defaultNow(),
  updatedAt: timestamp("updated_at", { withTimezone: true }).notNull().defaultNow(),
});

export const accounts = pgTable("accounts", {
  id: uuid("id").primaryKey().defaultRandom(),
  userId: uuid("user_id").notNull().references(() => users.id, { onDelete: "cascade" }),
  type: text("type").notNull(),
  provider: text("provider").notNull(),
  providerAccountId: text("provider_account_id").notNull(),
  refresh_token: text("refresh_token"),
  access_token: text("access_token"),
  expires_at: integer("expires_at"),
  token_type: text("token_type"),
  scope: text("scope"),
  id_token: text("id_token"),
  session_state: text("session_state"),
});

export const sessions = pgTable("sessions", {
  sessionToken: text("session_token").primaryKey(),
  userId: uuid("user_id").notNull().references(() => users.id, { onDelete: "cascade" }),
  expires: timestamp("expires", { withTimezone: true }).notNull(),
});

export const verificationTokens = pgTable("verification_tokens", {
  identifier: text("identifier").notNull(),
  token: text("token").unique().notNull(),
  expires: timestamp("expires", { withTimezone: true }).notNull(),
});

export const carriers = pgTable("carriers", {
  id: uuid("id").primaryKey().defaultRandom(),
  name: text("name").notNull(),
  slug: text("slug").unique().notNull(),
  country: text("country"),
  apiAvailable: boolean("api_available").notNull().default(false),
  scrapeAvailable: boolean("scrape_available").notNull().default(false),
  baseUrl: text("base_url"),
  trackingUrlTemplate: text("tracking_url_template"),
  createdAt: timestamp("created_at", { withTimezone: true }).notNull().defaultNow(),
});

export const shipments = pgTable("shipments", {
  id: uuid("id").primaryKey().defaultRandom(),
  trackingNumber: text("tracking_number").notNull(),
  carrierId: uuid("carrier_id").notNull().references(() => carriers.id),
  userId: uuid("user_id").references(() => users.id),
  status: text("status").notNull().default("pending"),
  serviceType: text("service_type"),
  weightKg: decimal("weight_kg", { precision: 8, scale: 3 }),
  originLat: decimal("origin_lat", { precision: 9, scale: 6 }),
  originLng: decimal("origin_lng", { precision: 9, scale: 6 }),
  originName: text("origin_name"),
  destLat: decimal("dest_lat", { precision: 9, scale: 6 }),
  destLng: decimal("dest_lng", { precision: 9, scale: 6 }),
  destName: text("dest_name"),
  shippedAt: timestamp("shipped_at", { withTimezone: true }),
  deliveredAt: timestamp("delivered_at", { withTimezone: true }),
  estimatedDelivery: timestamp("estimated_delivery", { withTimezone: true }),
  source: text("source").notNull().default("user"),
  createdAt: timestamp("created_at", { withTimezone: true }).notNull().defaultNow(),
  updatedAt: timestamp("updated_at", { withTimezone: true }).notNull().defaultNow(),
});

export const shipmentEvents = pgTable("shipment_events", {
  id: uuid("id").primaryKey().defaultRandom(),
  shipmentId: uuid("shipment_id").notNull().references(() => shipments.id, { onDelete: "cascade" }),
  status: text("status").notNull(),
  locationLat: decimal("location_lat", { precision: 9, scale: 6 }),
  locationLng: decimal("location_lng", { precision: 9, scale: 6 }),
  locationName: text("location_name"),
  description: text("description"),
  rawData: jsonb("raw_data"),
  eventTime: timestamp("event_time", { withTimezone: true }).notNull(),
  createdAt: timestamp("created_at", { withTimezone: true }).notNull().defaultNow(),
});

export const predictions = pgTable("predictions", {
  id: uuid("id").primaryKey().defaultRandom(),
  shipmentId: uuid("shipment_id").notNull().references(() => shipments.id, { onDelete: "cascade" }),
  predictedDelivery: timestamp("predicted_delivery", { withTimezone: true }).notNull(),
  confidenceLow: timestamp("confidence_low", { withTimezone: true }),
  confidenceHigh: timestamp("confidence_high", { withTimezone: true }),
  confidencePct: decimal("confidence_pct", { precision: 5, scale: 2 }),
  modelVersion: text("model_version").notNull(),
  features: jsonb("features"),
  createdAt: timestamp("created_at", { withTimezone: true }).notNull().defaultNow(),
});

export const carrierRoutes = pgTable("carrier_routes", {
  id: uuid("id").primaryKey().defaultRandom(),
  carrierId: uuid("carrier_id").notNull().references(() => carriers.id),
  originRegion: text("origin_region").notNull(),
  destRegion: text("dest_region").notNull(),
  serviceType: text("service_type"),
  avgDays: decimal("avg_days", { precision: 6, scale: 2 }),
  medianDays: decimal("median_days", { precision: 6, scale: 2 }),
  p10Days: decimal("p10_days", { precision: 6, scale: 2 }),
  p90Days: decimal("p90_days", { precision: 6, scale: 2 }),
  sampleCount: integer("sample_count").notNull().default(0),
  routeHops: jsonb("route_hops"),
  updatedAt: timestamp("updated_at", { withTimezone: true }).notNull().defaultNow(),
});

export const scrapeJobs = pgTable("scrape_jobs", {
  id: uuid("id").primaryKey().defaultRandom(),
  shipmentId: uuid("shipment_id").references(() => shipments.id, { onDelete: "set null" }),
  carrierId: uuid("carrier_id").notNull().references(() => carriers.id),
  trackingNumber: text("tracking_number").notNull(),
  status: text("status").notNull().default("pending"),
  attempts: integer("attempts").notNull().default(0),
  lastError: text("last_error"),
  nextAttemptAt: timestamp("next_attempt_at", { withTimezone: true }).notNull().defaultNow(),
  createdAt: timestamp("created_at", { withTimezone: true }).notNull().defaultNow(),
  completedAt: timestamp("completed_at", { withTimezone: true }),
});

export const modelVersions = pgTable("model_versions", {
  id: uuid("id").primaryKey().defaultRandom(),
  modelName: text("model_name").notNull(),
  version: text("version").notNull(),
  metrics: jsonb("metrics"),
  trainedAt: timestamp("trained_at", { withTimezone: true }).notNull().defaultNow(),
  isActive: boolean("is_active").notNull().default(false),
});
