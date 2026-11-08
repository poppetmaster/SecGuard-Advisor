/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./src/secguard_advisor/web/templates/**/*.html",
    "./src/secguard_advisor/web/static/js/**/*.js",
  ],
  theme: {
    extend: {},
  },
  plugins: [require("flowbite/plugin")],
};
