import type { NextConfig } from "next";

/**
 * Security headers for the HTML app.
 *
 * The API sets its own, stricter set. These protect the pages the browser
 * actually renders. A CSP is deliberately not set here: Next.js injects inline
 * bootstrap scripts, so a correct policy needs nonce plumbing through the
 * document — worth doing before a public launch, but a broken CSP is worse than
 * none, and the remaining headers cover the common cases.
 */
const securityHeaders = [
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  {
    key: "Permissions-Policy",
    value: "camera=(), microphone=(), geolocation=(), interest-cohort=()",
  },
];

const nextConfig: NextConfig = {
  // Emits a self-contained server bundle for the runtime Docker stage.
  output: "standalone",

  // Type errors must fail the build, not be silently shipped. Next 16 no longer
  // runs ESLint during `build`, so `npm run lint` is a separate CI step.
  typescript: { ignoreBuildErrors: false },

  poweredByHeader: false,
  reactStrictMode: true,

  async headers() {
    return [{ source: "/:path*", headers: securityHeaders }];
  },
};

export default nextConfig;
