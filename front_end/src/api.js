import * as SecureStore from 'expo-secure-store';
import { Platform } from 'react-native';

export const API_URL = (process.env.EXPO_PUBLIC_API_URL || 'http://localhost:8000').replace(/\/$/, '');

const ACCESS_KEY = 'academia_access_token';
const REFRESH_KEY = 'academia_refresh_token';
const EMAIL_KEY = 'academia_email';
let sessionExpiredHandler = null;
let sessionExpirationTimer = null;

const storage = {
  async getItem(key) {
    if (Platform.OS === 'web') return globalThis.localStorage?.getItem(key) ?? null;
    return SecureStore.getItemAsync(key);
  },
  async setItem(key, value) {
    if (Platform.OS === 'web') return globalThis.localStorage?.setItem(key, value);
    return SecureStore.setItemAsync(key, value);
  },
  async deleteItem(key) {
    if (Platform.OS === 'web') return globalThis.localStorage?.removeItem(key);
    return SecureStore.deleteItemAsync(key);
  },
};

export function setSessionExpiredHandler(handler) {
  sessionExpiredHandler = handler;
}

function tokenExpired(token) {
  try {
    const payload = token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/');
    const normalized = payload.padEnd(payload.length + ((4 - (payload.length % 4)) % 4), '=');
    const decoded = JSON.parse(globalThis.atob(normalized));
    return !decoded.exp || decoded.exp * 1000 <= Date.now();
  } catch {
    return true;
  }
}

function tokenRemainingMs(token) {
  try {
    const payload = token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/');
    const normalized = payload.padEnd(payload.length + ((4 - (payload.length % 4)) % 4), '=');
    const decoded = JSON.parse(globalThis.atob(normalized));
    return decoded.exp * 1000 - Date.now();
  } catch {
    return 0;
  }
}

function scheduleSessionExpiration(refreshToken) {
  if (sessionExpirationTimer) clearTimeout(sessionExpirationTimer);
  const remaining = tokenRemainingMs(refreshToken);
  if (remaining <= 0) return;
  sessionExpirationTimer = setTimeout(async () => {
    if (tokenExpired(refreshToken)) await expireSession();
    else scheduleSessionExpiration(refreshToken);
  }, Math.min(remaining, 2147483647));
}

async function expireSession() {
  await clearSession();
  sessionExpiredHandler?.();
}

export async function saveSession(data, email) {
  const writes = [
    storage.setItem(ACCESS_KEY, data.access_token),
    storage.setItem(REFRESH_KEY, data.refresh_token),
  ];
  if (email) writes.push(storage.setItem(EMAIL_KEY, email));
  await Promise.all(writes);
  scheduleSessionExpiration(data.refresh_token);
}

export async function clearSession() {
  if (sessionExpirationTimer) clearTimeout(sessionExpirationTimer);
  sessionExpirationTimer = null;
  await Promise.all([
    storage.deleteItem(ACCESS_KEY),
    storage.deleteItem(REFRESH_KEY),
    storage.deleteItem(EMAIL_KEY),
  ]);
}

export async function hasSession() {
  const refreshToken = await storage.getItem(REFRESH_KEY);
  if (!refreshToken) return false;
  if (tokenExpired(refreshToken)) {
    await expireSession();
    return false;
  }
  scheduleSessionExpiration(refreshToken);
  return true;
}

export async function getSessionEmail() {
  return (await storage.getItem(EMAIL_KEY)) || '';
}

function errorMessage(body, fallback) {
  if (typeof body?.detail === 'string') return body.detail;
  if (Array.isArray(body?.detail)) return body.detail[0]?.msg || fallback;
  return body?.message || fallback;
}

async function rawRequest(path, options = {}, token) {
  let response;
  try {
    response = await fetch(`${API_URL}${path}`, {
      ...options,
      headers: {
        Accept: 'application/json',
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...options.headers,
      },
    });
  } catch {
    throw new Error('Não foi possível conectar ao servidor. Confira sua internet e o endereço da API.');
  }

  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    const error = new Error(errorMessage(body, 'Não foi possível concluir a solicitação.'));
    error.status = response.status;
    throw error;
  }
  return body;
}

async function refreshAccessToken() {
  const refreshToken = await storage.getItem(REFRESH_KEY);
  if (!refreshToken || tokenExpired(refreshToken)) {
    await expireSession();
    throw new Error('Sua sessão expirou. Entre novamente.');
  }
  try {
    const session = await rawRequest('/refresh', { method: 'POST' }, refreshToken);
    await saveSession(session);
    return session.access_token;
  } catch (error) {
    if (error.status === 401) {
      await expireSession();
      throw new Error('Sua sessão expirou. Entre novamente.');
    }
    throw error;
  }
}

export async function request(path, options = {}, authenticated = false) {
  if (!authenticated) return rawRequest(path, options);
  let accessToken = await storage.getItem(ACCESS_KEY);
  try {
    return await rawRequest(path, options, accessToken);
  } catch (error) {
    if (error.status !== 401) throw error;
    accessToken = await refreshAccessToken();
    return rawRequest(path, options, accessToken);
  }
}

export const api = {
  login: (email, senha) => request('/login', { method: 'POST', body: JSON.stringify({ email, senha }) }),
  register: (data) => request('/cadastro', { method: 'POST', body: JSON.stringify(data) }),
  resendConfirmation: (email) => request('/reenviar-email', { method: 'POST', body: JSON.stringify({ email }) }),
  forgotPassword: (email) => request('/senha/esqueci-senha', { method: 'POST', body: JSON.stringify({ email }) }),
  resetPassword: (token, senha, confirmar_senha) => request(`/senha/redefinir-senha?token=${encodeURIComponent(token)}`, { method: 'PATCH', body: JSON.stringify({ senha, confirmar_senha }) }),
  changeName: (nome) => request('/alterar-nome', { method: 'PATCH', body: JSON.stringify({ nome }) }, true),
  requestPasswordChange: (email) => request('/senha/enviar-email-alteracao', { method: 'POST', body: JSON.stringify({ email }) }, true),
  deleteAccount: (senha, confirmar_senha) => request('/deletar-conta', { method: 'POST', body: JSON.stringify({ senha, confirmar_senha }) }, true),
  resendDeleteEmail: () => request('/deletar-conta/reenviar-email', { method: 'POST' }, true),
};
