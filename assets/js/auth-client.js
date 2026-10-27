/**
 * Viral-X Secure Frontend Authentication Client Module
 * Sprint 5.5 — End-to-End Authentication Integration
 *
 * Security Architecture & Threat Model:
 * 1. Storage Strategy:
 *    - Short-lived Access Token is kept strictly in-memory (closure scope).
 *      This prevents persistent XSS token theft via localStorage.
 *    - Refresh Token is held in sessionStorage (cleared when the browser tab closes),
 *      or can be rotated automatically.
 * 2. Automatic Token Renewal:
 *    - authenticatedFetch() transparently handles 401 Unauthorized responses by
 *      attempting a single token refresh against POST /api/v1/auth/refresh.
 *    - If refresh fails or tokens are revoked, the session is safely invalidated.
 * 3. Logout & Token Invalidation:
 *    - Invoking logout() sends a revocation request to POST /api/v1/auth/logout,
 *      ensuring the server marks both access and refresh tokens as revoked.
 * 4. Isolation:
 *    - Does not modify legacy Node.js endpoints (/api/chat).
 *    - Points to Python FastAPI backend endpoints (/api/v1/*).
 */

(function (root, factory) {
  if (typeof module === 'object' && module.exports) {
    module.exports = factory();
  } else {
    root.ViralXAuth = factory();
  }
})(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  // In-memory token storage (XSS Mitigation)
  let _accessToken = null;
  let _tokenExpiresAt = null;
  let _currentUser = null;
  let _isRefreshing = false;
  let _refreshQueue = [];

  const STORAGE_KEY_REFRESH = 'vx_rt_session';
  const API_BASE = ''; // Relative path (proxied) or configurable

  // Callbacks
  const _subscribers = new Set();

  function _notifySubscribers() {
    const state = {
      isAuthenticated: Boolean(_accessToken),
      user: _currentUser,
    };
    _subscribers.forEach((cb) => {
      try {
        cb(state);
      } catch (err) {
        console.error('[ViralXAuth] Subscriber error:', err);
      }
    });
  }

  function getStoredRefreshToken() {
    try {
      return sessionStorage.getItem(STORAGE_KEY_REFRESH);
    } catch {
      return null;
    }
  }

  function setStoredRefreshToken(token) {
    try {
      if (token) {
        sessionStorage.setItem(STORAGE_KEY_REFRESH, token);
      } else {
        sessionStorage.removeItem(STORAGE_KEY_REFRESH);
      }
    } catch (err) {
      console.warn('[ViralXAuth] Could not write refresh token to sessionStorage:', err);
    }
  }

  /**
   * Logs in a user with username and password.
   * Obtains access and refresh tokens from /api/v1/auth/token.
   */
  async function login(username, password) {
    if (!username || !password) {
      throw new Error('Username and password are required.');
    }

    const res = await fetch(`${API_BASE}/api/v1/auth/token`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
    });

    if (!res.ok) {
      const errorData = await res.json().catch(() => ({ detail: 'Authentication failed' }));
      throw new Error(errorData.detail || errorData.error || `Login failed with status ${res.status}`);
    }

    const data = await res.json();
    _accessToken = data.accessToken || data.access_token;
    const expiresIn = data.expiresIn || data.expires_in || 3600;
    _tokenExpiresAt = Date.now() + (expiresIn - 30) * 1000;

    const refreshToken = data.refreshToken || data.refresh_token;
    setStoredRefreshToken(refreshToken);

    // Fetch principal profile
    await fetchCurrentUser();
    _notifySubscribers();

    return {
      success: true,
      user: _currentUser,
    };
  }

  /**
   * Refreshes the access token using the stored refresh token.
   * Handles refresh token rotation transparently.
   */
  async function refreshAccessToken() {
    const refreshToken = getStoredRefreshToken();
    if (!refreshToken) {
      clearSession();
      throw new Error('No refresh token available.');
    }

    if (_isRefreshing) {
      // Queue concurrent callers until current refresh completes
      return new Promise((resolve, reject) => {
        _refreshQueue.push({ resolve, reject });
      });
    }

    _isRefreshing = true;

    try {
      const res = await fetch(`${API_BASE}/api/v1/auth/refresh`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refreshToken }),
      });

      if (!res.ok) {
        clearSession();
        throw new Error(`Refresh failed with HTTP ${res.status}`);
      }

      const data = await res.json();
      _accessToken = data.accessToken || data.access_token;
      const expiresIn = data.expiresIn || data.expires_in || 3600;
      _tokenExpiresAt = Date.now() + (expiresIn - 30) * 1000;

      // Update rotated refresh token
      const newRefreshToken = data.refreshToken || data.refresh_token;
      if (newRefreshToken) {
        setStoredRefreshToken(newRefreshToken);
      }

      _refreshQueue.forEach(({ resolve }) => resolve(_accessToken));
      _refreshQueue = [];

      _notifySubscribers();
      return _accessToken;
    } catch (err) {
      _refreshQueue.forEach(({ reject }) => reject(err));
      _refreshQueue = [];
      clearSession();
      throw err;
    } finally {
      _isRefreshing = false;
    }
  }

  /**
   * Fetches the current authenticated principal profile from /api/v1/auth/me.
   */
  async function fetchCurrentUser() {
    if (!_accessToken) return null;

    try {
      const res = await fetch(`${API_BASE}/api/v1/auth/me`, {
        headers: {
          Authorization: `Bearer ${_accessToken}`,
        },
      });

      if (res.ok) {
        _currentUser = await res.json();
        return _currentUser;
      }
    } catch (err) {
      console.warn('[ViralXAuth] Failed to fetch current user profile:', err);
    }
    return null;
  }

  /**
   * Logs out the user by explicitly revoking the active access and refresh tokens.
   */
  async function logout() {
    const refreshToken = getStoredRefreshToken();

    if (_accessToken) {
      try {
        await fetch(`${API_BASE}/api/v1/auth/logout`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${_accessToken}`,
          },
          body: JSON.stringify({ refreshToken: refreshToken || null }),
        });
      } catch (err) {
        console.warn('[ViralXAuth] Non-fatal logout network warning:', err);
      }
    }

    clearSession();
  }

  function clearSession() {
    _accessToken = null;
    _tokenExpiresAt = null;
    _currentUser = null;
    setStoredRefreshToken(null);
    _notifySubscribers();
  }

  /**
   * Authenticated Fetch Wrapper
   * Injects the Bearer token and automatically retries once upon receiving 401 Unauthorized.
   */
  async function authenticatedFetch(input, init = {}) {
    // If token is near expiration, refresh proactively
    if (_accessToken && _tokenExpiresAt && Date.now() > _tokenExpiresAt) {
      try {
        await refreshAccessToken();
      } catch (err) {
        console.info('[ViralXAuth] Proactive refresh skipped:', err.message);
      }
    }

    const headers = new Headers(init.headers || {});
    if (_accessToken && !headers.has('Authorization')) {
      headers.set('Authorization', `Bearer ${_accessToken}`);
    }

    const modifiedInit = {
      ...init,
      headers,
    };

    let response = await fetch(input, modifiedInit);

    // If 401 Unauthorized and we have a refresh token, attempt token refresh and replay request once
    if (response.status === 401 && getStoredRefreshToken()) {
      try {
        const newAccessToken = await refreshAccessToken();
        headers.set('Authorization', `Bearer ${newAccessToken}`);
        response = await fetch(input, {
          ...init,
          headers,
        });
      } catch (refreshErr) {
        console.warn('[ViralXAuth] Token refresh attempt failed during authenticatedFetch:', refreshErr.message);
      }
    }

    return response;
  }

  function subscribe(callback) {
    _subscribers.add(callback);
    callback({
      isAuthenticated: Boolean(_accessToken),
      user: _currentUser,
    });
    return () => _subscribers.delete(callback);
  }

  return {
    login,
    logout,
    refreshAccessToken,
    authenticatedFetch,
    fetchCurrentUser,
    subscribe,
    isAuthenticated: () => Boolean(_accessToken),
    getCurrentUser: () => _currentUser,
    getAccessToken: () => _accessToken,
  };
});
