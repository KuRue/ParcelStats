export function normalizeTrackingNumber(value: string): string {
  return value.replace(/\s+/g, "").toUpperCase();
}

export function detectCarrierSlug(value: string): string | null {
  const trackingNumber = normalizeTrackingNumber(value);

  if (!trackingNumber) return null;
  if (/^1Z[0-9A-Z]{16}$/.test(trackingNumber)) return "ups";
  if (/^E[ES][0-9A-Z]{20,}$/.test(trackingNumber)) return "speedpak";
  if (/^[A-Z]{2}\d{9}[A-Z]{2}$/.test(trackingNumber)) return "usps";
  if (/^(92|93|94|95)\d{20,24}$/.test(trackingNumber)) return "usps";
  if (/^\d{10}$/.test(trackingNumber)) return "dhl-express";
  if (/^\d{12}$/.test(trackingNumber) || /^\d{15}$/.test(trackingNumber)) {
    return "fedex";
  }
  if (/^\d{20,22}$/.test(trackingNumber)) return "fedex";

  return null;
}
