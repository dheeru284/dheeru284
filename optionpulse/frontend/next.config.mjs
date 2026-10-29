/** @type {import('next').NextConfig} */
const backend = process.env.OPTIONPULSE_BACKEND_URL ?? "http://127.0.0.1:8000";

const nextConfig = {
  reactStrictMode: true,
  // The browser only ever talks to this origin; Next proxies /api to FastAPI.
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${backend}/api/:path*` }];
  },
};

export default nextConfig;
