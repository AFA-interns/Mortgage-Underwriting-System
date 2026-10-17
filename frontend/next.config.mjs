/** @type {import('next').NextConfig} */
const nextConfig = {
  agentRules: false,
  typescript: {
    ignoreBuildErrors: true,
  },
  images: {
    unoptimized: true,
  },
  async rewrites() {
    return [
      {
        source: '/api/v1/:path*',
        destination: 'http://127.0.0.1:8000/api/v1/:path*'
      },
      {
        // Pre-existing Decision Agent evaluation endpoints, outside /api/v1.
        source: '/evaluation/:path*',
        destination: 'http://127.0.0.1:8000/evaluation/:path*'
      }
    ]
  }
}

export default nextConfig
