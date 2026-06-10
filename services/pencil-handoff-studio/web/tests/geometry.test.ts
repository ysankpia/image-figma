import { describe, expect, it } from 'vitest';
import { candidateAt, hitHandle, moveBox, resizeBox, sliceAt } from '../src/geometry';
import type { Candidate, ManualSlice } from '../src/types';

describe('geometry', () => {
  it('moves boxes within bounds', () => {
    expect(moveBox({ x: 5, y: 5, width: 10, height: 10 }, 100, 100, { width: 50, height: 40 })).toEqual({
      x: 40,
      y: 30,
      width: 10,
      height: 10,
    });
  });

  it('resizes boxes by handle', () => {
    expect(resizeBox({ x: 10, y: 10, width: 20, height: 20 }, 'se', 5, 7, { width: 100, height: 100 })).toEqual({
      x: 10,
      y: 10,
      width: 25,
      height: 27,
    });
  });

  it('hits smallest candidate first', () => {
    const candidates: Candidate[] = [
      candidate('big', { x: 0, y: 0, width: 100, height: 100 }, 0.9),
      candidate('small', { x: 10, y: 10, width: 20, height: 20 }, 0.2),
    ];
    expect(candidateAt(candidates, new Set(), { x: 15, y: 15 })?.id).toBe('small');
  });

  it('hits active handles and slices', () => {
    const slice: ManualSlice = {
      id: 's1',
      pageId: 'page_0001',
      name: 's1',
      displayName: 's1',
      kind: 'image',
      bbox: { x: 10, y: 10, width: 20, height: 20 },
      selected: true,
      source: 'manual',
      candidateIds: [],
      tags: [],
    };
    expect(hitHandle(slice, { x: 30, y: 30 })).toBe('se');
    expect(sliceAt([slice], { x: 12, y: 12 })?.id).toBe('s1');
  });
});

function candidate(id: string, bbox: Candidate['bbox'], confidence: number): Candidate {
  return { id, pageId: 'page_0001', kind: 'image', bbox, confidence, sources: ['fake'], reason: 'fake' };
}
