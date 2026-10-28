import type { NextConfig } from "next";

/**
 * The API is proxied through this app rather than called directly.
 *
 * The session cookie is SameSite=Lax, which browsers do not send on
 * cross-site requests. In development that is invisible: localhost:3000 and
 * localhost:8000 differ only by port, so they are the same site and the
 * cookie is sent. In production the frontend and backend sit on different
 * registrable domains (vercel.app and hf.space are both public suffixes), so
 * the request is cross-site and the cookie would be dropped -- sign-in would
 * appear to succeed and every later request would be anonymous.
 *
 * Proxying means the browser only ever talks to this origin, so the cookie
 * stays first-party and Lax keeps its CSRF protection. The alternative,
 * SameSite=None, would send the cookie on genuinely cross-site requests and
 * require separate CSRF defences.
 *
 * It also applies in development, so dev and production behave the same way
 * and this class of bug cannot reappear in only one of them.
 */
const BACKEND_ORIGIN = process.env.BACKEND_ORIGIN ?? "http://localhost:8000";

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      { source: "/api/:path*", destination: `${BACKEND_ORIGIN}/api/:path*` },
    ];
  },
  cacheComponents: true,
  partialPrefetching: true,
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;
