
export const CATEGORIES = [
  'COD',
  'DSA',
  'APTI',
  'COMM',
  'OOD',
  'AI',
  'CLOUD',
  'SQL',
  'SWE',
  'SYSD',
  'NETW',
  'OS',
  'OTHER',
];

export const blankProfile = {
  name: '',
  email: '',
  education: '',
  skills: [],
  hackathons: [],
  internships: [],
  experience: [],
  certifications: [],
  preferred_roles: [],
  projects: [],
  cv_file: '',
};

const STORAGE_KEY = 'radix-api-base-url';

const ENV_API =
  import.meta.env.VITE_API_BASE_URL ||
  import.meta.env.VITE_API_URL ||
  'http://127.0.0.1:8000';

const normalizeBase = (value) =>
  String(value || '').trim().replace(/\/+$/, '');

export function getApiBase() {
  try {
    return (
      normalizeBase(window.localStorage.getItem(STORAGE_KEY)) ||
      normalizeBase(ENV_API)
    );
  } catch {
    return normalizeBase(ENV_API);
  }
}

export function setApiBase(value) {
  const clean = normalizeBase(value);

  if (!/^https?:\/\//i.test(clean)) {
    throw new Error(
      'Backend URL must start with http:// or https://'
    );
  }

  try {
    window.localStorage.setItem(STORAGE_KEY, clean);
  } catch {
    throw new Error(
      'Browser storage is unavailable, so the backend URL could not be saved.'
    );
  }

  return clean;
}

// Convert FastAPI/Pydantic errors into readable messages.
export function errText(d, fallback) {
  const x = d && d.detail;

  if (!x) return fallback;

  if (typeof x === 'string') return x;

  if (Array.isArray(x)) {
    return (
      x
        .map((e) =>
          e.message
            ? (e.field ? e.field + ': ' : '') + e.message
            : (e.loc ? e.loc.slice(1).join('.') + ': ' : '') +
              (e.msg || '')
        )
        .join('; ') || fallback
    );
  }

  return fallback;
}

// Centralized fetch, JSON parsing and error handling.
export async function call(
  path,
  { method = 'GET', json, form, signal } = {},
  fallback = 'Request failed'
) {
  const base = getApiBase();

  const opts = {
    method,
    signal,
  };

  if (json !== undefined) {
    opts.headers = {
      'Content-Type': 'application/json',
    };

    opts.body = JSON.stringify(json);
  }

  if (form) {
    opts.body = form;
  }

  let r;

  try {
    r = await fetch(base + path, opts);
  } catch (e) {
    if (e?.name === 'AbortError') {
      throw e;
    }

    throw new Error(
      'Cannot reach the API at ' +
        base +
        ' (' +
        (e && e.message ? e.message : 'network error') +
        '). Is the backend running, and is CORS configured?'
    );
  }

  let d = null;

  try {
    d = await r.json();
  } catch {
    // Response was not valid JSON.
  }

  if (!r.ok) {
    throw new Error(
      errText(d, fallback + ' (HTTP ' + r.status + ')')
    );
  }

  return d;
}

export const companyIdForTalent = (id) =>
  String(id).startsWith('supabase:')
    ? id
    : Number(id);

export const companyIdForMatch = (id) =>
  String(id).startsWith('supabase:')
    ? Number(String(id).split(':')[1])
    : Number(id);
