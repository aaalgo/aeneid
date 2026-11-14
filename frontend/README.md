# Aeneid frontend

A static Svelte 5 application. API requests go to the same origin in production.

Start the existing Flask backend with `python server.py`, then:

```sh
cd frontend
npm install
npm run dev
```

Vite proxies `/api` to `http://127.0.0.1:5000` during development.

Build for Flask:

```sh
cd frontend
npm run build
```

This replaces `../static/` with compiled HTML, JavaScript, and CSS. Visit
`http://127.0.0.1:5000/` with Flask running. No Node server is needed in production.
