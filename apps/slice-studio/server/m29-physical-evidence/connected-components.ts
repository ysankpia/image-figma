import type { ForegroundMask, PixelComponent } from "./types";

export function connectedComponents(mask: ForegroundMask, minArea: number, maxAreaRatio: number): PixelComponent[] {
  const visited = new Uint8Array(mask.data.length);
  const components: PixelComponent[] = [];
  const maxArea = Math.trunc(mask.width * mask.height * maxAreaRatio);
  let nextId = 1;
  for (let y = 0; y < mask.height; y += 1) {
    for (let x = 0; x < mask.width; x += 1) {
      const index = y * mask.width + x;
      if (visited[index] || !mask.data[index]) continue;
      const component = flood(nextId, mask, visited, x, y);
      if (component.area >= minArea && (maxArea <= 0 || component.area <= maxArea)) {
        components.push(component);
        nextId += 1;
      }
    }
  }
  return components;
}

function flood(id: number, mask: ForegroundMask, visited: Uint8Array, startX: number, startY: number): PixelComponent {
  const queue = [startY * mask.width + startX];
  visited[queue[0]] = 1;
  let head = 0;
  let minX = startX;
  let maxX = startX;
  let minY = startY;
  let maxY = startY;
  const pixels: number[] = [];
  while (head < queue.length) {
    const index = queue[head];
    head += 1;
    pixels.push(index);
    const x = index % mask.width;
    const y = Math.trunc(index / mask.width);
    if (x < minX) minX = x;
    if (x > maxX) maxX = x;
    if (y < minY) minY = y;
    if (y > maxY) maxY = y;
    pushNeighbor(mask, visited, queue, x + 1, y);
    pushNeighbor(mask, visited, queue, x - 1, y);
    pushNeighbor(mask, visited, queue, x, y + 1);
    pushNeighbor(mask, visited, queue, x, y - 1);
  }
  return {
    id,
    area: pixels.length,
    pixels,
    bbox: {
      x: minX,
      y: minY,
      width: maxX - minX + 1,
      height: maxY - minY + 1
    }
  };
}

function pushNeighbor(mask: ForegroundMask, visited: Uint8Array, queue: number[], x: number, y: number): void {
  if (x < 0 || y < 0 || x >= mask.width || y >= mask.height) return;
  const index = y * mask.width + x;
  if (visited[index] || !mask.data[index]) return;
  visited[index] = 1;
  queue.push(index);
}
