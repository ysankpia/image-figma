FROM oven/bun:1.3.5 AS deps
WORKDIR /app
COPY package.json ./
RUN bun install --no-progress

FROM oven/bun:1.3.5 AS builder
WORKDIR /app
ENV NEXT_PUBLIC_SLICE_STUDIO_API_URL=
ENV SLICE_STUDIO_INTERNAL_API_URL=http://127.0.0.1:4110
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN bun run build

FROM oven/bun:1.3.5 AS runner
WORKDIR /app
ENV NODE_ENV=production
ENV NEXT_PUBLIC_SLICE_STUDIO_API_URL=
ENV SLICE_STUDIO_INTERNAL_API_URL=http://127.0.0.1:4110
ENV SLICE_STUDIO_API_HOST=0.0.0.0
ENV SLICE_STUDIO_API_PORT=4110
ENV SLICE_STUDIO_WEB_PORT=3010
ENV SLICE_STUDIO_STORAGE_ROOT=/data/slice-studio
COPY --from=builder /app ./
RUN mkdir -p .next/standalone/.next/static .next/standalone/apps/slice-studio/.next/static \
  && cp -R .next/static/. .next/standalone/.next/static/ \
  && cp -R .next/static/. .next/standalone/apps/slice-studio/.next/static/
RUN mkdir -p /data/slice-studio
VOLUME ["/data/slice-studio"]
EXPOSE 3010 4110
CMD ["bun", "run", "start:prod"]
