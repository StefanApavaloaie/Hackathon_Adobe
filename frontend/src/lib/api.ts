const API_URL = import.meta.env.VITE_API_URL as string | undefined;

export async function apiGet<T>(path: string): Promise<T> {
  if (!API_URL) {
    throw new Error("VITE_API_URL is not set. Copy frontend/.env.example to frontend/.env.");
  }

  let response: Response;
  try {
    response = await fetch(`${API_URL.replace(/\/$/, "")}${path}`);
  } catch {
    throw new Error(`Could not reach the backend at ${API_URL}.`);
  }

  if (!response.ok) {
    throw new Error(`The backend returned ${response.status} for ${path}.`);
  }
  return response.json() as Promise<T>;
}
