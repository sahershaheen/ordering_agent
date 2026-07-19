/**
 * Typed client for the Flavour & Rush FastAPI backend.
 *
 * The backend runs separately on localhost:8000 (see server.py at the
 * project root). Override the base URL with NEXT_PUBLIC_API_URL if needed.
 */

export const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// --- Response types (mirror api/schemas.py) ---------------------------------

export interface Source {
  page: number;
  snippet: string;
  confidence: number;
}

export interface ChatResponse {
  session_id: string;
  reply: string;
  sources: Source[];
  confidence: number | null;
}

export interface VoiceChatResponse extends ChatResponse {
  transcript: string;
  audio_base64: string;
}

export interface OrderItem {
  item: string;
  qty: number;
  unit_price: number;
}

export interface OrderResponse {
  order_id: number;
  order_type: string;
  items: OrderItem[];
  total_price: number;
  payment_method: string;
  delivery_address: string | null;
  estimated_time: string;
}

export interface OrderStatus {
  order_id: number;
  order_type: string;
  status: string;
  status_label: string;
  items: { item: string; qty: number; unit_price: number }[];
  total_price: number;
  created_at: string;
}

export interface ReservationResponse {
  reservation_id: number;
  customer_name: string;
  phone: string;
  date: string;
  time: string;
  guests: number;
  special_requests: string | null;
  status: string;
}

export interface MenuPassage {
  page: number;
  content: string;
  confidence: number;
}

export interface MenuResponse {
  query: string;
  passages: MenuPassage[];
}

export interface OrderRecord {
  order_id: number;
  customer_name: string;
  phone: string;
  order_type: string;
  items: { item: string; qty: number; unit_price: number }[];
  total_price: number;
  payment_method: string;
  status: string;
  delivery_address: string | null;
  created_at: string;
}

export interface ReservationRecord {
  reservation_id: number;
  customer_name: string;
  phone: string;
  date: string;
  time: string;
  guests: number;
  special_requests: string | null;
  status: string;
}

export interface HealthResponse {
  status: "ok" | "degraded";
  components: Record<string, string>;
}

/** Error carrying the human-readable `detail` message from FastAPI. */
export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, init);
  } catch {
    throw new ApiError(
      "Cannot reach the server. Is the backend running on port 8000?",
      0,
    );
  }

  if (!response.ok) {
    let detail = `Request failed (${response.status})`;
    try {
      const body = await response.json();
      if (typeof body.detail === "string") detail = body.detail;
    } catch {
      // non-JSON error body: keep the generic message
    }
    throw new ApiError(detail, response.status);
  }
  return response.json();
}

function post<T>(path: string, body: unknown): Promise<T> {
  return request<T>(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

// --- Endpoints ----------------------------------------------------------------

export function sendChat(sessionId: string, message: string) {
  return post<ChatResponse>("/chat", { session_id: sessionId, message });
}

export function sendVoiceChat(sessionId: string, wav: Blob) {
  const form = new FormData();
  form.append("audio", wav, "speech.wav");
  form.append("session_id", sessionId);
  return request<VoiceChatResponse>("/voice-chat", {
    method: "POST",
    body: form,
  });
}

export function placeOrder(body: {
  full_name: string;
  phone: string;
  items: OrderItem[];
  payment_method: string;
  delivery_address?: string;
  email?: string;
}) {
  return post<OrderResponse>("/order", body);
}

export function trackOrders(params: { order_id?: string; phone?: string }) {
  const query = new URLSearchParams();
  if (params.order_id) query.set("order_id", params.order_id);
  if (params.phone) query.set("phone", params.phone);
  return request<OrderStatus[]>(`/order-status?${query}`);
}

export function bookReservation(body: {
  customer_name: string;
  phone: string;
  date: string;
  time: string;
  guests: number;
  special_requests?: string;
}) {
  return post<ReservationResponse>("/reservation", body);
}

export function cancelReservation(reservationId: number, phone: string) {
  return post<{ reservation_id: number; status: string }>(
    "/cancel-reservation",
    { reservation_id: reservationId, phone },
  );
}

export function searchMenu(query: string) {
  return request<MenuResponse>(`/menu?query=${encodeURIComponent(query)}`);
}

export function getHealth() {
  return request<HealthResponse>("/health");
}

export function listAllOrders() {
  return request<OrderRecord[]>("/orders");
}

export function listAllReservations() {
  return request<ReservationRecord[]>("/reservations");
}
