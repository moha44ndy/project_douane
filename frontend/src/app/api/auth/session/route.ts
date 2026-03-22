import { NextRequest, NextResponse } from "next/server";

const COOKIE_NAME = "sb-access-token";

export async function POST(req: NextRequest) {
  let body: unknown;
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON" }, { status: 400 });
  }

  const accessToken =
    body &&
    typeof body === "object" &&
    "access_token" in body &&
    typeof (body as { access_token: unknown }).access_token === "string"
      ? (body as { access_token: string }).access_token
      : null;

  if (!accessToken) {
    return NextResponse.json({ error: "access_token required" }, { status: 400 });
  }

  const expiresIn =
    body &&
    typeof body === "object" &&
    "expires_in" in body &&
    typeof (body as { expires_in: unknown }).expires_in === "number"
      ? (body as { expires_in: number }).expires_in
      : undefined;

  const maxAge = Math.min(
    Math.max(expiresIn ?? 3600, 60),
    60 * 60 * 24 * 30
  );

  const res = NextResponse.json({ ok: true });
  res.cookies.set(COOKIE_NAME, accessToken, {
    path: "/",
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    maxAge,
  });
  return res;
}

export async function DELETE() {
  const res = NextResponse.json({ ok: true });
  res.cookies.set(COOKIE_NAME, "", {
    path: "/",
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax",
    maxAge: 0,
  });
  return res;
}
