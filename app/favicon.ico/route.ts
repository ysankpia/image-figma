const favicon = Uint8Array.from(Buffer.from(
  "AAABAAEAEBAAAAEAIABoBAAAFgAAACgAAAAQAAAAIAAAAAEAIAAAAAAAQAQAAAAAAAAAAAAAAAAAAAAAAAAAAAAA////AP///wD///8A////AP///wD///8A////AP///wD///8A////AP///wD///8A////AP///wD///8A////AP///wD///8A////AP///wD///8A////AP///wD///8A////AP///wD///8A////AP///wD///8A////AP///wD///8A////AAAAAAAAAAD///8A////AP///wD///8A////AP///wD///8A////AP///wD///8A////AAAAAAAAAAD///8A////AP///wD///8A////AP///wAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA////AP///wD///8A////AAAAAAAAAAD///8A////AP///wD///8A////AP///wD///8A////AP///wD///8A////AAAAAAAAAAD///8A////AP///wD///8A////AP///wAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA////AP///wD///8A////AAAAAAAAAAD///8A////AP///wD///8A////AP///wD///8A////AP///wD///8A////AAAAAAAAAAD///8A////AP///wD///8A////AP///wAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA////AP///wD///8A////AAAAAAAAAAD///8A////AP///wD///8A////AP///wD///8A////AP///wD///8A////AAAAAAAAAAD///8A////AP///wD///8A////AP///wD///8A////AP///wD///8A////AP///wD///8A////AP///wD///8A////AP///wD///8A////AP///wD///8A////AP///wD///8A////AP///wD///8A////AP///wD///8A////AP///wD///8A",
  "base64"
));

export function GET(): Response {
  return new Response(favicon, {
    headers: {
      "content-type": "image/x-icon",
      "cache-control": "public, max-age=86400"
    }
  });
}
