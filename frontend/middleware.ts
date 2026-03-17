import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";
import { jwtVerify } from "jose";

const PROTECTED_PATHS = ["/", "/historique", "/admin"];

async function isTokenValid(token: string): Promise<boolean> {
  try {
    const secret = process.env.SUPABASE_JWT_SECRET;
    if (!secret) return false;
    await jwtVerify(token, new TextEncoder().encode(secret));
    return true;
  } catch {
    return false;
  }
}

export async function middleware(req: NextRequest) {
  const { pathname } = req.nextUrl;

  const isProtected = PROTECTED_PATHS.some(
    (p) => pathname === p || pathname.startsWith(p + "/")
  );
  if (!isProtected) {
    return NextResponse.next();
  }

  const token = req.cookies.get("sb-access-token")?.value;
  if (!token || !(await isTokenValid(token))) {
    const loginUrl = new URL("/login", req.url);
    loginUrl.searchParams.set("redirectedFrom", pathname);
    return NextResponse.redirect(loginUrl);
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/", "/historique/:path*", "/admin/:path*"],
};