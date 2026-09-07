/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Enable the new stable React Compiler (React 19+)
  reactCompiler: true, 
  turbopack:{},
  // Note: Turbopack is the default in v16. 
  // If you must use this Webpack watch logic, 
  // run 'next dev --webpack' or 'next build --webpack'
  webpack(config, { dev }) {
    if (dev) {
      config.watchOptions = {
        ...config.watchOptions,
        aggregateTimeout: 300,
        poll: 1000,
        ignored: /node_modules/,
      };
    }
    return config;
  },
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: 'http://127.0.0.1:8001/api/:path*',
      },
    ];
  },
};

export default nextConfig;
