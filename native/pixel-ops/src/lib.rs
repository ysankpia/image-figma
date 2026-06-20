use napi_derive::napi;
use napi::bindgen_prelude::Buffer;

fn clamp(value: i32, min: i32, max: i32) -> i32 {
    value.max(min).min(max)
}

fn color_distance(r1: u8, g1: u8, b1: u8, r2: u8, g2: u8, b2: u8) -> f64 {
    let dr = r1 as f64 - r2 as f64;
    let dg = g1 as f64 - g2 as f64;
    let db = b1 as f64 - b2 as f64;
    (dr * dr + dg * dg + db * db).sqrt()
}

/// In-place iterative inpainting of masked pixels using neighboring non-masked pixels.
/// target_data: RGBA pixel buffer (modified in place)
/// width, height: image dimensions
/// rect_left, rect_top, rect_width, rect_height: region of interest
/// mask_data: binary mask (1 = to-be-inpainted, 0 = keep), same dimensions as rect
/// fallback_r/g/b: fallback color for unresolvable pixels
#[napi]
pub fn inpaint_text_mask(
    mut target_data: Buffer,
    width: u32,
    height: u32,
    rect_left: u32,
    rect_top: u32,
    rect_width: u32,
    rect_height: u32,
    mask_data: Buffer,
    fallback_r: u8,
    fallback_g: u8,
    fallback_b: u8,
) -> Buffer {
    let target = target_data.as_mut();
    let mask = mask_data.as_ref();
    let w = width as usize;
    let _h = height as usize;
    let rl = rect_left as usize;
    let rt = rect_top as usize;
    let rw = rect_width as usize;
    let rh = rect_height as usize;
    let mask_len = rw * rh;

    if mask_len == 0 || mask.len() < mask_len {
        return target_data;
    }

    let mut resolved = vec![0u8; mask_len];
    let mut unresolved = 0usize;

    for (i, &m) in mask.iter().enumerate().take(mask_len) {
        if m != 0 {
            unresolved += 1;
        } else {
            resolved[i] = 1;
        }
    }

    if unresolved == 0 {
        return target_data;
    }

    let max_iterations = clamp(((rw.max(rw)) as f64 * 0.35).ceil() as i32, 8, 36) as usize;

    for _iteration in 0..max_iterations {
        if unresolved == 0 {
            break;
        }
        let mut updates: Vec<(usize, u8, u8, u8)> = Vec::new();

        for local_y in 0..rh {
            let row = local_y * rw;
            for local_x in 0..rw {
                let idx = row + local_x;
                if mask[idx] == 0 || resolved[idx] != 0 {
                    continue;
                }
                let mut sum_r: u32 = 0;
                let mut sum_g: u32 = 0;
                let mut sum_b: u32 = 0;
                let mut count: u32 = 0;

                for dy in -1i32..=1 {
                    for dx in -1i32..=1 {
                        if dx == 0 && dy == 0 {
                            continue;
                        }
                        let nx = local_x as i32 + dx;
                        let ny = local_y as i32 + dy;
                        if nx < 0 || ny < 0 || nx >= rw as i32 || ny >= rh as i32 {
                            continue;
                        }
                        let nidx = (ny as usize) * rw + (nx as usize);
                        if resolved[nidx] == 0 {
                            continue;
                        }
                        let px = rl + nx as usize;
                        let py = rt + ny as usize;
                        if px >= w || py >= _h {
                            continue;
                        }
                        let offset = (py * w + px) * 4;
                        if target[offset + 3] < 200 {
                            continue;
                        }
                        sum_r += target[offset] as u32;
                        sum_g += target[offset + 1] as u32;
                        sum_b += target[offset + 2] as u32;
                        count += 1;
                    }
                }

                if count > 0 {
                    updates.push((
                        idx,
                        (sum_r / count) as u8,
                        (sum_g / count) as u8,
                        (sum_b / count) as u8,
                    ));
                }
            }
        }

        if updates.is_empty() {
            break;
        }

        for (idx, r, g, b) in &updates {
            let local_x = idx % rw;
            let local_y = idx / rw;
            let px = rl + local_x;
            let py = rt + local_y;
            if px >= w || py >= _h {
                continue;
            }
            let offset = (py * w + px) * 4;
            target[offset] = *r;
            target[offset + 1] = *g;
            target[offset + 2] = *b;
            target[offset + 3] = 255;
            resolved[*idx] = 1;
            unresolved -= 1;
        }
    }

    // Fill remaining unresolved pixels with fallback color
    for local_y in 0..rh {
        let row = local_y * rw;
        for local_x in 0..rw {
            let idx = row + local_x;
            if mask[idx] == 0 || resolved[idx] != 0 {
                continue;
            }
            let px = rl + local_x;
            let py = rt + local_y;
            if px >= w || py >= _h {
                continue;
            }
            let offset = (py * w + px) * 4;
            target[offset] = fallback_r;
            target[offset + 1] = fallback_g;
            target[offset + 2] = fallback_b;
            target[offset + 3] = 255;
        }
    }

    target_data
}

/// Dilate a binary mask by `radius` pixels (Manhattan distance).
/// Returns a new mask buffer.
#[napi]
pub fn dilate_text_mask(mask: Buffer, width: u32, height: u32, radius: u32) -> Buffer {
    let src = mask.as_ref();
    let w = width as usize;
    let h = height as usize;
    let len = w * h;
    if len == 0 || src.len() < len {
        return mask;
    }
    if radius == 0 {
        return mask;
    }

    let r = radius as i32;
    let mut result = vec![0u8; len];

    for y in 0..h {
        let row = y * w;
        for x in 0..w {
            let idx = row + x;
            if src[idx] != 0 {
                for dy in -r..=r {
                    for dx in -r..=r {
                        let nx = x as i32 + dx;
                        let ny = y as i32 + dy;
                        if nx < 0 || ny < 0 || nx >= w as i32 || ny >= h as i32 {
                            continue;
                        }
                        let nidx = (ny as usize) * w + (nx as usize);
                        result[nidx] = 1;
                    }
                }
            }
        }
    }

    Buffer::from(result)
}

/// Clear alpha channel in a rectangular region.
/// target_data: RGBA buffer (modified in place)
#[napi]
pub fn clear_alpha_rect(
    mut target_data: Buffer,
    width: u32,
    height: u32,
    bbox_x: u32,
    bbox_y: u32,
    bbox_w: u32,
    bbox_h: u32,
) -> Buffer {
    let target = target_data.as_mut();
    let w = width as usize;
    let h = height as usize;
    let left = bbox_x.min(w as u32) as usize;
    let top = bbox_y.min(h as u32) as usize;
    let right = (left + bbox_w as usize).min(w);
    let bottom = (top + bbox_h as usize).min(h);

    for y in top..bottom {
        let row = y * w;
        for x in left..right {
            target[(row + x) * 4 + 3] = 0;
        }
    }

    target_data
}

/// Find the bounding box of non-transparent alpha content.
/// Returns [x, y, width, height] or null if no content.
#[napi]
pub fn alpha_content_bbox(data: Buffer, width: u32, height: u32) -> Option<Vec<u32>> {
    let src = data.as_ref();
    let w = width as usize;
    let h = height as usize;
    let mut left = w as i32;
    let mut top = h as i32;
    let mut right: i32 = -1;
    let mut bottom: i32 = -1;

    for y in 0..h {
        let row = y * w;
        for x in 0..w {
            if src[(row + x) * 4 + 3] < 10 {
                continue;
            }
            let xi = x as i32;
            let yi = y as i32;
            if xi < left {
                left = xi;
            }
            if yi < top {
                top = yi;
            }
            if xi > right {
                right = xi;
            }
            if yi > bottom {
                bottom = yi;
            }
        }
    }

    if right < left || bottom < top {
        None
    } else {
        Some(vec![
            left as u32,
            top as u32,
            (right - left + 1) as u32,
            (bottom - top + 1) as u32,
        ])
    }
}

/// Apply shape cutout: flood-fill from edges to remove background-connected pixels.
/// Returns a new RGBA buffer with background pixels alpha-cleared.
#[napi]
pub fn apply_shape_cutout(
    source_data: Buffer,
    width: u32,
    height: u32,
    mode: Option<String>,
    target_left: Option<u32>,
    target_top: Option<u32>,
    target_width: Option<u32>,
    target_height: Option<u32>,
) -> Buffer {
    let src = source_data.as_ref();
    let w = width as usize;
    let h = height as usize;
    let len = w * h;
    if w < 4 || h < 4 || src.len() < len * 4 {
        return source_data;
    }

    // Estimate background color from edges
    let (bg_r, bg_g, bg_b) = estimate_background(src, w, h);

    let is_card = mode.as_deref() == Some("card");
    let mut background_mask = vec![0u8; len];
    let blocked_mask = if is_card {
        build_interior_guard(
            w,
            h,
            target_left.map(|v| v as usize),
            target_top.map(|v| v as usize),
            target_width.map(|v| v as usize),
            target_height.map(|v| v as usize),
        )
    } else {
        vec![0u8; len]
    };
    let mut outside_mask = vec![0u8; len];
    let mut queue: Vec<usize> = Vec::new();
    let mut result = Vec::with_capacity(src.len());
    result.extend_from_slice(src);

    let threshold = 42u32;
    for i in 0..len {
        let offset = i * 4;
        if src[offset + 3] < 10 {
            background_mask[i] = 1;
            continue;
        }
        let dist = color_distance(
            src[offset], src[offset + 1], src[offset + 2],
            bg_r, bg_g, bg_b,
        );
        if (dist as u32) <= threshold {
            background_mask[i] = 1;
        }
    }

    // Seed flood fill from edges
    for x in 0..w {
        push_flood_seed(x, 0, w, h, &background_mask, &blocked_mask, &mut outside_mask, &mut queue);
        push_flood_seed(x, h - 1, w, h, &background_mask, &blocked_mask, &mut outside_mask, &mut queue);
    }
    for y in 0..h {
        push_flood_seed(0, y, w, h, &background_mask, &blocked_mask, &mut outside_mask, &mut queue);
        push_flood_seed(w - 1, y, w, h, &background_mask, &blocked_mask, &mut outside_mask, &mut queue);
    }

    let mut cursor = 0;
    while cursor < queue.len() {
        let idx = queue[cursor];
        let x = idx % w;
        let y = idx / w;
        cursor += 1;
        if x + 1 < w {
            push_flood_seed(x + 1, y, w, h, &background_mask, &blocked_mask, &mut outside_mask, &mut queue);
        }
        if x > 0 {
            push_flood_seed(x - 1, y, w, h, &background_mask, &blocked_mask, &mut outside_mask, &mut queue);
        }
        if y + 1 < h {
            push_flood_seed(x, y + 1, w, h, &background_mask, &blocked_mask, &mut outside_mask, &mut queue);
        }
        if y > 0 {
            push_flood_seed(x, y - 1, w, h, &background_mask, &blocked_mask, &mut outside_mask, &mut queue);
        }
    }

    let outside_ratio = queue.len() as f64 / len as f64;
    if outside_ratio < 0.003 || outside_ratio > 0.92 {
        return source_data;
    }

    for &idx in &queue {
        result[idx * 4 + 3] = 0;
    }

    Buffer::from(result)
}

fn push_flood_seed(
    x: usize, y: usize, w: usize, h: usize,
    background_mask: &[u8], blocked_mask: &[u8],
    outside_mask: &mut [u8], queue: &mut Vec<usize>,
) {
    if x >= w || y >= h {
        return;
    }
    let idx = y * w + x;
    if background_mask[idx] == 0 || blocked_mask[idx] != 0 || outside_mask[idx] != 0 {
        return;
    }
    outside_mask[idx] = 1;
    queue.push(idx);
}

fn build_interior_guard(
    w: usize, h: usize,
    left_opt: Option<usize>, top_opt: Option<usize>,
    width_opt: Option<usize>, height_opt: Option<usize>,
) -> Vec<u8> {
    let mut guard = vec![0u8; w * h];
    let (tl, tt, tw, th) = match (left_opt, top_opt, width_opt, height_opt) {
        (Some(l), Some(t), Some(wi), Some(hi)) => (l, t, wi, hi),
        _ => return guard,
    };
    let min_side = tw.min(th);
    let area = tw * th;
    if min_side < 72 || area < 4096 {
        return guard;
    }
    let inset = clamp((min_side as f64 * 0.06).round() as i32, 8, 16) as usize;
    let left = tl.saturating_add(inset).min(w);
    let top = tt.saturating_add(inset).min(h);
    let right = (tl + tw).saturating_sub(inset).min(w);
    let bottom = (tt + th).saturating_sub(inset).min(h);
    if right <= left || bottom <= top {
        return guard;
    }
    for y in top..bottom {
        let row = y * w;
        for x in left..right {
            guard[row + x] = 1;
        }
    }
    guard
}

fn estimate_background(src: &[u8], w: usize, h: usize) -> (u8, u8, u8) {
    let stride = (w.max(h) / 64).max(1);
    let mut samples_r: Vec<u8> = Vec::new();
    let mut samples_g: Vec<u8> = Vec::new();
    let mut samples_b: Vec<u8> = Vec::new();

    let mut push = |x: usize, y: usize| {
        let offset = (y * w + x) * 4;
        if src[offset + 3] >= 10 {
            samples_r.push(src[offset]);
            samples_g.push(src[offset + 1]);
            samples_b.push(src[offset + 2]);
        }
    };

    let mut x = 0;
    while x < w {
        push(x, 0);
        push(x, h - 1);
        x += stride;
    }
    let mut y = 0;
    while y < h {
        push(0, y);
        push(w - 1, y);
        y += stride;
    }

    if samples_r.is_empty() {
        return (255, 255, 255);
    }

    samples_r.sort_unstable();
    samples_g.sort_unstable();
    samples_b.sort_unstable();
    let mid = samples_r.len() / 2;
    (samples_r[mid], samples_g[mid], samples_b[mid])
}

/// Check if a rounded rect contains a point.
#[napi]
pub fn point_inside_rounded_rect(
    local_x: f64,
    local_y: f64,
    width: f64,
    height: f64,
    radius: f64,
) -> bool {
    if radius <= 0.0 {
        return true;
    }
    if local_x >= radius && local_x <= width - radius {
        return true;
    }
    if local_y >= radius && local_y <= height - radius {
        return true;
    }
    let center_x = if local_x < radius { radius } else { width - radius };
    let center_y = if local_y < radius { radius } else { height - radius };
    let dx = local_x - center_x;
    let dy = local_y - center_y;
    dx * dx + dy * dy <= radius * radius + 0.75
}
