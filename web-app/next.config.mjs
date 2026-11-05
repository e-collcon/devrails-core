// web-app — next.config.mjs
// DevRails PoC | PRD-001
// Next.js 14.2 does not load next.config.ts (support arrived in Next 15), so the
// scaffold's next.config.ts stopped `next build`. Same (empty) config, as .mjs.

/** @type {import('next').NextConfig} */
const nextConfig = {
  // Keep PoC config minimal per PRD-001 §10.2:
  // no SSR complexity, server actions, or custom API routes.
  reactStrictMode: true,
};

export default nextConfig;
