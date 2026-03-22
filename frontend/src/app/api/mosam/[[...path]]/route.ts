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
    if (!HOP_BY_HOP.has(key.toLowerCase())) {
      outHeaders.set(key, value);
    }
  });

  const method = req.method;
  let body: ArrayBuffer | undefined;
  if (method !== "GET" && method !== "HEAD") {
    body = await req.arrayBuffer();
  }

  const upstreamRes = await fetch(targetUrl, {
    method,
    headers: outHeaders,
    body: body && body.byteLength > 0 ? body : undefined,
  });

  const resHeaders = new Headers(upstreamRes.headers);
  return new NextResponse(upstreamRes.body, {
    status: upstreamRes.status,
    statusText: upstreamRes.statusText,
    headers: resHeaders,
  });
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
