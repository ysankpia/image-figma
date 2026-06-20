import type { WorkerInput, WorkerOutput } from "./export-page-worker";

class WorkerSlot {
  worker: Worker;
  busy = false;
  private currentResolve: ((result: WorkerOutput) => void) | null = null;
  private currentReject: ((error: Error) => void) | null = null;

  constructor() {
    this.worker = new Worker(new URL("./export-page-worker.ts", import.meta.url).href);
    this.worker.onmessage = (event: MessageEvent<WorkerOutput>) => {
      const resolve = this.currentResolve;
      const reject = this.currentReject;
      this.currentResolve = null;
      this.currentReject = null;
      this.busy = false;
      if (resolve && reject) {
        if (event.data.error) {
          reject(new Error(event.data.error));
        } else {
          resolve(event.data);
        }
      }
    };
    this.worker.onerror = (err) => {
      const reject = this.currentReject;
      this.currentResolve = null;
      this.currentReject = null;
      this.busy = false;
      if (reject) {
        reject(err instanceof Error ? err : new Error(String(err)));
      }
    };
  }

  post(input: WorkerInput): Promise<WorkerOutput> {
    this.busy = true;
    return new Promise<WorkerOutput>((resolve, reject) => {
      this.currentResolve = resolve;
      this.currentReject = reject;
      const copy = Buffer.from(input.originalBuffer);
      this.worker.postMessage({ ...input, originalBuffer: copy }, { transfer: [copy.buffer] });
    });
  }

  terminate(): void {
    this.worker.terminate();
  }
}

export class PageWorkerPool {
  private slots: WorkerSlot[] = [];
  private terminated = false;

  constructor(count: number) {
    for (let i = 0; i < count; i += 1) {
      this.slots.push(new WorkerSlot());
    }
  }

  process(input: WorkerInput): Promise<WorkerOutput> {
    if (this.terminated) return Promise.reject(new Error("Worker pool terminated"));
    const slot = this.slots.find((s) => !s.busy);
    if (slot) return slot.post(input);
    return new Promise<WorkerOutput>((resolve, reject) => {
      const check = () => {
        if (this.terminated) {
          reject(new Error("Worker pool terminated"));
          return;
        }
        const free = this.slots.find((s) => !s.busy);
        if (free) {
          free.post(input).then(resolve, reject);
        } else {
          setTimeout(check, 10);
        }
      };
      check();
    });
  }

  terminate(): void {
    this.terminated = true;
    for (const slot of this.slots) {
      slot.terminate();
    }
    this.slots = [];
  }
}

export function createPageWorkerPool(count: number): PageWorkerPool {
  return new PageWorkerPool(count);
}
