export const fmt = (n: number) => n.toLocaleString("en-AU");
export const km = (m: number) => (m >= 1000 ? `${(m / 1000).toFixed(1)} km` : `${m} m`);
export const mins = (m: number) => (m >= 120 ? `${Math.floor(m / 60)} h ${m % 60} min` : `${m} min`);
