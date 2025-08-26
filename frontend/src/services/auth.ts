// Simple Keycloak OIDC authentication helper (Auth Code + PKCE)
// Focus: minimal login/logout & user info extraction for demo.

interface AppAuthConfig {
  KEYCLOAK_URL: string;
  KEYCLOAK_REALM: string;
  KEYCLOAK_CLIENT_ID: string;
  KEYCLOAK_REDIRECT_URI: string;
}

interface Tokens {
  access_token: string;
  refresh_token?: string;
  id_token?: string;
  expires_at: number; // epoch seconds
}

function getCfg(): AppAuthConfig {
  const cfg: any = (window as any).APP_CONFIG || {};
  return cfg;
}

const STORAGE_KEY = 'df_auth_tokens_v1';

export function loadTokens(): Tokens | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const t: Tokens = JSON.parse(raw);
    if (!t.access_token) return null;
    return t;
  } catch {
    return null;
  }
}

export function saveTokens(t: Tokens) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(t));
}

export function clearTokens() {
  localStorage.removeItem(STORAGE_KEY);
}

export function isExpired(t: Tokens | null): boolean {
  if (!t) return true;
  const now = Math.floor(Date.now() / 1000);
  return now >= (t.expires_at - 30); // 30s skew
}

// Decode JWT payload (no verification; dev only)
export function parseJwtPayload(token: string): any {
  try {
    const parts = token.split('.');
    if (parts.length !== 3) return null;
    const payload = atob(parts[1].replace(/-/g, '+').replace(/_/g, '/'));
    return JSON.parse(decodeURIComponent(escape(payload)));
  } catch {
    return null;
  }
}

function randomString(size = 43): string {
  const arr = new Uint8Array(size);
  crypto.getRandomValues(arr);
  return Array.from(arr, b => 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_'.charAt(b % 64)).join('');
}

async function sha256(base: string) {
  const data = new TextEncoder().encode(base);
  const digest = await crypto.subtle.digest('SHA-256', data);
  return btoa(String.fromCharCode(...new Uint8Array(digest)))
    .replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/,'');
}

export interface AuthState {
  loading: boolean;
  isAuthenticated: boolean;
  username?: string;
  isVip?: boolean;
  rawTokens?: Tokens | null;
}

export async function startLogin() {
  const cfg = getCfg();
  const state = randomString(16);
  const verifier = randomString(64);
  const challenge = await sha256(verifier);
  sessionStorage.setItem('pkce_verifier', verifier);
  sessionStorage.setItem('oidc_state', state);
  const authUrl = `${cfg.KEYCLOAK_URL}/realms/${cfg.KEYCLOAK_REALM}/protocol/openid-connect/auth?` + new URLSearchParams({
    client_id: cfg.KEYCLOAK_CLIENT_ID,
    redirect_uri: cfg.KEYCLOAK_REDIRECT_URI,
    response_type: 'code',
    scope: 'openid profile',
    code_challenge: challenge,
    code_challenge_method: 'S256',
    state,
  });
  window.location.href = authUrl;
}

export async function exchangeCode(code: string, state: string): Promise<Tokens | null> {
  const expectedState = sessionStorage.getItem('oidc_state');
  const verifier = sessionStorage.getItem('pkce_verifier');
  sessionStorage.removeItem('oidc_state');
  if (!verifier || state !== expectedState) return null;
  const cfg = getCfg();
  const tokenUrl = `${cfg.KEYCLOAK_URL}/realms/${cfg.KEYCLOAK_REALM}/protocol/openid-connect/token`;
  const body = new URLSearchParams({
    grant_type: 'authorization_code',
    code,
    redirect_uri: cfg.KEYCLOAK_REDIRECT_URI,
    client_id: cfg.KEYCLOAK_CLIENT_ID,
    code_verifier: verifier,
  });
  const resp = await fetch(tokenUrl, { method: 'POST', body });
  if (!resp.ok) return null;
  const json = await resp.json();
  const expires_at = Math.floor(Date.now() / 1000) + (json.expires_in || 300);
  const t: Tokens = { access_token: json.access_token, refresh_token: json.refresh_token, id_token: json.id_token, expires_at };
  saveTokens(t);
  return t;
}

export function buildAuthState(): AuthState {
  const t = loadTokens();
  if (!t || isExpired(t)) return { loading: false, isAuthenticated: false };
  const payload = parseJwtPayload(t.access_token);
  const username = payload?.preferred_username || payload?.email || payload?.sub;
  // VIP detection: prefer realm role 'vip'; fallback to custom claim / attribute if later mapped
  const roles: string[] = payload?.realm_access?.roles || [];
  const isVip = !!(
    (Array.isArray(roles) && roles.includes('vip')) ||
    payload?.vip === true ||
    payload?.is_vip === true ||
    (Array.isArray(payload?.is_vip) && payload.is_vip.includes('true'))
  );
  return { loading: false, isAuthenticated: true, username, isVip, rawTokens: t };
}

export function logout() {
  const cfg = getCfg();
  const t = loadTokens();
  clearTokens();
  // Front-channel logout (best-effort). Keycloak redirect doesn't strictly require id_token_hint for public client.
  const url = `${cfg.KEYCLOAK_URL}/realms/${cfg.KEYCLOAK_REALM}/protocol/openid-connect/logout?` + new URLSearchParams({
    client_id: cfg.KEYCLOAK_CLIENT_ID,
    post_logout_redirect_uri: cfg.KEYCLOAK_REDIRECT_URI,
    ...(t?.id_token ? { id_token_hint: t.id_token } : {})
  });
  window.location.href = url;
}
