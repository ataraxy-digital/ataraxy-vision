import { next } from '@vercel/edge';

// IP/geo language routing with a manual override.
//
// Priority order:
//   1. Explicit locale path (/es, /pt) is served as-is.
//   2. A `lang` cookie set by the footer language toggle wins over geo -
//      `en` keeps the visitor on the English root, es/pt redirect to that
//      prefix. The cookie is scoped to .ataraxydigital.com so a choice made on
//      one property carries across the whole suite.
//   3. Otherwise the country of the IP picks the language (English default).
//
// Any path with a file extension and Next internals are skipped via `matcher`.

const SPANISH = new Set([
  'ES','MX','AR','CO','PE','VE','CL','EC','GT','CU','BO','DO','HN','PY','SV','NI','CR','PA','UY','PR','GQ',
]);
const PORTUGUESE = new Set(['BR','PT','AO','MZ','CV','GW','ST','TL']);

export const config = {
  matcher: ['/((?!_next/|.*\\.[a-zA-Z0-9]+$).*)'],
};

function cookieLang(request: Request): string {
  const m = /(?:^|;\s*)lang=(en|es|pt)\b/.exec(request.headers.get('cookie') || '');
  return m ? m[1] : '';
}

export default function middleware(request: Request) {
  const url = new URL(request.url);
  const path = url.pathname;

  // already in a localized subtree → leave alone
  if (/^\/(es|pt)(\/|$)/.test(path)) return next();

  // explicit user choice from the language toggle wins over geolocation
  const chosen = cookieLang(request);
  if (chosen === 'en') return next(); // English stays at the root

  let prefix = '';
  if (chosen === 'es' || chosen === 'pt') {
    prefix = '/' + chosen;
  } else {
    const country = (request.headers.get('x-vercel-ip-country') || '').toUpperCase();
    if (PORTUGUESE.has(country)) prefix = '/pt';
    else if (SPANISH.has(country)) prefix = '/es';
  }

  if (!prefix) return next(); // English stays at the root

  url.pathname = prefix + (path === '/' ? '/' : path);
  return Response.redirect(url, 307);
}
