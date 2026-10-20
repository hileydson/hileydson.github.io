// Cloudflare Worker in front of the GitHub Pages store.
//
// Decky's store request carries an X-Decky-Version header, so the Steam client sends a
// CORS preflight (OPTIONS) first. GitHub Pages answers OPTIONS with 405 and the store
// never loads; this Worker answers the preflight and proxies the JSON from Pages.
//
// Store URL in Decky: https://<worker-name>.<account>.workers.dev
//   GET /?sort_by=...  -> https://hileydson.github.io/            (plugin list)
//   GET /versions      -> https://hileydson.github.io/versions/   (update check)

const ORIGIN = "https://hileydson.github.io";

const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, HEAD, OPTIONS",
  "Access-Control-Allow-Headers": "*",
  "Access-Control-Max-Age": "600",
};

export default {
  async fetch(request) {
    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: CORS });
    }
    if (request.method !== "GET" && request.method !== "HEAD") {
      return new Response("Method not allowed", { status: 405, headers: CORS });
    }

    const url = new URL(request.url);
    // Pages serves folders as <path>/index.html; ask for the trailing slash directly
    // so there is no redirect. The query (sort_by) is ignored: the list is static.
    let path = url.pathname.replace(/\/+$/, "");
    path = path === "" ? "/" : path + "/";

    const upstream = await fetch(ORIGIN + path, { cf: { cacheTtl: 300, cacheEverything: true } });
    return new Response(request.method === "HEAD" ? null : upstream.body, {
      status: upstream.status,
      headers: { ...CORS, "Content-Type": "application/json; charset=utf-8", "Cache-Control": "public, max-age=300" },
    });
  },
};
