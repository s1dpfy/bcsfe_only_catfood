export async function onRequest({ request }) {
  return Response.redirect(new URL("/admin.html", request.url), 302);
}
