// Shared by both branches. Frozen after step 0: change it only through a pull request to main.
import { getAccessToken } from "./auth";

const API_URL = import.meta.env.VITE_API_URL as string | undefined;

export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(method: "GET" | "POST", path: string, body?: unknown): Promise<T> {
  if (!API_URL) {
    throw new ApiError(0, "VITE_API_URL is not set. Copy frontend/.env.example to frontend/.env.");
  }

  const headers: Record<string, string> = {};
  const token = await getAccessToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  if (body !== undefined) headers["Content-Type"] = "application/json";

  let response: Response;
  try {
    response = await fetch(`${API_URL.replace(/\/$/, "")}${path}`, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    throw new ApiError(0, `Could not reach the backend at ${API_URL}.`);
  }

  if (!response.ok) {
    const detail = await response
      .json()
      .then((data: { detail?: unknown }) => (typeof data.detail === "string" ? data.detail : null))
      .catch(() => null);
    throw new ApiError(response.status, detail ?? `The backend returned ${response.status} for ${path}.`);
  }
  return (response.status === 204 ? undefined : await response.json()) as T;
}

export const apiGet = <T>(path: string) => request<T>("GET", path);
export const apiPost = <T>(path: string, body?: unknown) => request<T>("POST", path, body);
