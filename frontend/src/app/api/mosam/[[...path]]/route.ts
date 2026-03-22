import { NextRequest, NextResponse } from "next/server";

export const maxDuration = 120;
export const dynamic = "force-dynamic";

const HOP_BY_HOP = new Set([
  "connection",
  "keep-alive",
  "proxy-authenticate",
  "proxy-authorization",
  "te",
  "trailers",
  "transfer-encoding",
  "upgrade",
  "host",
]);

/** En-têtes navigateur / Vercel inutiles ou trop lourds pour FastAPI (ex. cookies énormes). */
const STRIP_TO_UPSTREAM = new Set([
  ...HOP_BY_HOP,
  "cookie",
  "x-vercel-id",
  "x-vercel-ja4-digest",
  "x-vercel-ip-as-number",
  "x-vercel-ip-continent",
  "x-vercel-ip-country",
  "x-vercel-ip-latitude",
  "x-vercel-ip-longitude",
  "x-vercel-ip-timezone",
  "x-vercel-oidc-token",
  "x-vercel-proxied-for",
  "x-vercel-sc-headers",
  "x-vercel-sc-host",
]);

async function proxy(
  req: NextRequest,
  params: { path?: string[] }
): Promise<NextResponse> {
  const upstreamRaw = process.env.MOSAM_API_UPSTREAM?.trim();
  if (!upstreamRaw) {
    return NextResponse.json(
      {
        error:
          "MOSAM_API_UPSTREAM non configuré sur Vercel (URL HTTP du backend FastAPI, variable serveur uniquement).",
      },
      { status: 502 }
    );
  }

  const upstream = upstreamRaw.replace(/\/+$/, "");
  const segments = params.path ?? [];
  const subpath = segments.join("/");
  const url = new URL(req.url);
  const targetUrl = subpath
    ? `${upstream}/${subpath}${url.search}`
    : `${upstream}${url.search}`;

  const outHeaders = new Headers();
  req.headers.forEach((value, key) => {
    if (!STRIP_TO_UPSTREAM.has(key.toLowerCase())) {
      outHeaders.set(key, value);
    }
  });

  const method = req.method;
  let body: ArrayBuffer | undefined;
  if (method !== "GET" && method !== "HEAD") {
    body = await req.arrayBuffer();
  }

  try {
    const upstreamRes = await fetch(targetUrl, {
      method,
      headers: outHeaders,
      body: body && body.byteLength > 0 ? body : undefined,
    });

    const resHeaders = new Headers(upstreamRes.headers);
    resHeaders.delete("set-cookie");
    return new NextResponse(upstreamRes.body, {
      status: upstreamRes.status,
      statusText: upstreamRes.statusText,
      headers: resHeaders,
    });
  } catch (e) {
    const technical = e instanceof Error ? e.message : String(e);
    console.error("[api/mosam proxy] fetch failed:", targetUrl, technical);
    return NextResponse.json(
      {
        error:
          "Le serveur Vercel n’a pas pu joindre MOSAM_API_UPSTREAM (timeout, refus de connexion ou réseau). Vérifiez que l’API écoute sur une IP/port accessibles depuis Internet (Compute OCI + règle entrante TCP 8080), pas seulement dans Oracle Cloud Shell.",
        detail: technical,
      },
      { status: 502 }
    );
  }
}

type RouteCtx = { params: Promise<{ path?: string[] }> };

export async function GET(req: NextRequest, ctx: RouteCtx) {
  return proxy(req, await ctx.params);
}

export async function POST(req: NextRequest, ctx: RouteCtx) {
  return proxy(req, await ctx.params);
}

export async function PUT(req: NextRequest, ctx: RouteCtx) {
  return proxy(req, await ctx.params);
}

export async function PATCH(req: NextRequest, ctx: RouteCtx) {
  return proxy(req, await ctx.params);
}

export async function DELETE(req: NextRequest, ctx: RouteCtx) {
  return proxy(req, await ctx.params);
}
