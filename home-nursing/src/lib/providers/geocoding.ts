export type GeocodeResult = { formattedAddress: string; lat: number; lng: number; pincode?: string; city?: string; state?: string; locality?: string };

export interface GeocodingProvider {
  readonly name: string;
  /** Returns [] when nothing found or the provider fails. Never invents coordinates. */
  search(query: string): Promise<GeocodeResult[]>;
}

export class GoogleGeocodingProvider implements GeocodingProvider {
  readonly name = "google-geocoding";
  constructor(private apiKey: string, private fetchImpl: typeof fetch = fetch) {}
  async search(query: string) {
    const url = `https://maps.googleapis.com/maps/api/geocode/json?region=in&components=country:IN&address=${encodeURIComponent(query)}&key=${this.apiKey}`;
    const res = await this.fetchImpl(url, { signal: AbortSignal.timeout(5000) }).catch(() => null);
    if (!res?.ok) return [];
    const json = (await res.json()) as { status: string; results?: { formatted_address: string; geometry: { location: { lat: number; lng: number } }; address_components: { long_name: string; types: string[] }[] }[] };
    if (json.status !== "OK") return [];
    return (json.results ?? []).slice(0, 5).map((r) => {
      const c = (t: string) => r.address_components.find((x) => x.types.includes(t))?.long_name;
      return { formattedAddress: r.formatted_address, lat: r.geometry.location.lat, lng: r.geometry.location.lng, pincode: c("postal_code"), city: c("locality") ?? c("administrative_area_level_2"), state: c("administrative_area_level_1"), locality: c("sublocality_level_1") ?? c("sublocality") };
    });
  }
}

/** DEVELOPMENT ONLY: a fixed gazetteer of demo localities so the address flow works offline. Labelled as such in the UI. */
export class DevGazetteerGeocoder implements GeocodingProvider {
  readonly name = "dev-gazetteer";
  private places: GeocodeResult[] = [
    { formattedAddress: "Koramangala, Bengaluru, Karnataka 560034", lat: 12.9352, lng: 77.6245, pincode: "560034", city: "Bengaluru", state: "Karnataka", locality: "Koramangala" },
    { formattedAddress: "Indiranagar, Bengaluru, Karnataka 560038", lat: 12.9784, lng: 77.6408, pincode: "560038", city: "Bengaluru", state: "Karnataka", locality: "Indiranagar" },
    { formattedAddress: "Jayanagar, Bengaluru, Karnataka 560041", lat: 12.925, lng: 77.5938, pincode: "560041", city: "Bengaluru", state: "Karnataka", locality: "Jayanagar" },
    { formattedAddress: "Whitefield, Bengaluru, Karnataka 560066", lat: 12.9698, lng: 77.75, pincode: "560066", city: "Bengaluru", state: "Karnataka", locality: "Whitefield" },
    { formattedAddress: "Andheri West, Mumbai, Maharashtra 400053", lat: 19.1363, lng: 72.8277, pincode: "400053", city: "Mumbai", state: "Maharashtra", locality: "Andheri West" },
  ];
  async search(q: string) {
    const s = q.toLowerCase();
    return this.places.filter((p) => p.formattedAddress.toLowerCase().includes(s) || (p.pincode && s.includes(p.pincode)));
  }
}
