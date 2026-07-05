// PostCSS configuration — required for Tailwind v3 to run during the Vite build.
// Without this file (and with no css.postcss block in vite.config.ts), Vite does
// not process the @tailwind directives in src/index.css, so no utility classes
// are generated and the app renders unstyled. ESM syntax because package.json
// declares "type": "module".
export default {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
  },
};
