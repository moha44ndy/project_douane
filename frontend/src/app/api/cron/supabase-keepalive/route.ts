import { NextRequest, NextResponse } from "next/server";

export const dynamic = "force-dynamic";

function unauthorized() {
  return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
}

export async function GET(req: NextRequest) {
  const expectedSecret = process.env.CRON_SECRET;
  const authorization = req.headers.get("authorization");

  if (!expectedSecret) {
    return NextResponse.json(
      { error: "CRON_SECRET is not configured" },
      { status: 500 }
    );
  }

  if (authorization !== `Bearer ${expectedSecret}`) {
    return unauthorized();
  }

  const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

  if (!supabaseUrl || !supabaseAnonKey) {
    return NextResponse.json(
      { error: "Supabase environment variables are missing" },
      { status: 500 }
    );
  }

  const url = `${supabaseUrl.replace(/\/$/, "")}/auth/v1/health`;

  try {
    const res = await fetch(url, {
      method: "GET",
      headers: {
        apikey: supabaseAnonKey,
      },
      cache: "no-store",
    });

    return NextResponse.json(
      {
        ok: res.ok,
        status: res.status,
        checkedAt: new Date().toISOString(),
      },
      { status: res.ok ? 200 : 502 }
    );
  } catch (error) {
    const detail = error instanceof Error ? error.message : String(error);
    return NextResponse.json(
      {
        ok: false,
        error: "Failed to reach Supabase",
        detail,
      },
      { status: 502 }
    );
  }
}
